import os
import logging
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.user import User
from app.middleware.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agente", tags=["agente"])

# ── Funciones que Gemini puede llamar ─────────────────────────────────────────

def _consultar_pagos_cliente(db, org_id, cliente_nombre, desde=None, hasta=None):
    from app.models.planilla import Planilla, PlanillaRow
    from app.models.cliente import Cliente

    clientes = db.query(Cliente).filter(
        Cliente.organizacion_id == org_id,
        Cliente.nombre.ilike(f"%{cliente_nombre}%"),
        Cliente.deleted_at.is_(None)
    ).all()
    if not clientes:
        return {"error": f"No se encontró cliente '{cliente_nombre}'"}

    resultados = []
    for c in clientes:
        q = db.query(func.sum(PlanillaRow.monto)).join(Planilla).filter(
            Planilla.cliente_id == c.id,
            Planilla.organizacion_id == org_id,
            PlanillaRow.status == "ok",
            Planilla.deleted_at.is_(None),
        )
        if desde:
            q = q.filter(PlanillaRow.fecha_acred >= desde)
        if hasta:
            q = q.filter(PlanillaRow.fecha_acred <= hasta)
        total = float(q.scalar() or 0)
        cant = db.query(func.count(PlanillaRow.id)).join(Planilla).filter(
            Planilla.cliente_id == c.id,
            Planilla.organizacion_id == org_id,
            PlanillaRow.status == "ok",
            Planilla.deleted_at.is_(None),
        ).scalar() or 0
        resultados.append({"cliente": c.nombre, "total_pagado": total, "cantidad_pagos": cant})
    return {"resultados": resultados}


def _consultar_cheques(db, org_id, estado=None):
    from app.models.cheque import Cheque

    q = db.query(Cheque).filter(Cheque.organizacion_id == org_id)
    if estado:
        q = q.filter(Cheque.estado == estado)
    cheques = q.all()

    por_estado: dict = {}
    for c in cheques:
        por_estado.setdefault(c.estado, {"cantidad": 0, "total": 0.0})
        por_estado[c.estado]["cantidad"] += 1
        por_estado[c.estado]["total"] += float(c.monto or 0)

    proximos = [
        {"numero": c.numero, "monto": float(c.monto or 0), "cliente": c.cliente_nombre,
         "vencimiento": str(c.fecha_deposito), "banco": c.banco_origen}
        for c in sorted(
            [x for x in cheques if x.estado == "pendiente"],
            key=lambda x: x.fecha_deposito or date.max
        )[:5]
    ]
    return {
        "total_cheques": len(cheques),
        "total_monto": sum(float(c.monto or 0) for c in cheques),
        "por_estado": por_estado,
        "proximos_a_vencer": proximos,
    }


def _consultar_saldo_caja(db, org_id):
    from app.models.caja import ArqueoDiario

    arqueo = db.query(ArqueoDiario).filter(
        ArqueoDiario.organizacion_id == org_id,
        ArqueoDiario.fecha == date.today()
    ).first()
    if not arqueo:
        return {"error": "No hay arqueo del día de hoy. Abrí la Caja para crearlo."}
    return {
        "fecha": str(arqueo.fecha),
        "saldo_inicial": float(arqueo.saldo_inicial or 0),
        "pesos_agregados": float(arqueo.pesos_agregados or 0),
        "pagos_realizados": float(arqueo.pagos_dia),
        "saldo_actual": float(arqueo.caja_restante),
        "total_fisico": float(arqueo.total_arqueo_fisico),
        "diferencia_cruce": float(arqueo.cruce),
    }


def _buscar_cliente(db, org_id, nombre):
    from app.models.cliente import Cliente

    clientes = db.query(Cliente).filter(
        Cliente.organizacion_id == org_id,
        Cliente.nombre.ilike(f"%{nombre}%"),
        Cliente.deleted_at.is_(None)
    ).limit(8).all()
    return {"clientes": [
        {"id": c.id, "nombre": c.nombre, "cuit": c.cuit, "cbu": c.cbu}
        for c in clientes
    ]}


def _resumen_financiero(db, org_id, mes=None, año=None):
    from app.models.planilla import Planilla, PlanillaRow
    from app.models.cheque import Cheque

    hoy = date.today()
    mes = int(mes) if mes else hoy.month
    año = int(año) if año else hoy.year

    total_cobrado = db.query(func.sum(PlanillaRow.monto)).join(Planilla).filter(
        Planilla.organizacion_id == org_id,
        PlanillaRow.status == "ok",
        Planilla.deleted_at.is_(None),
        func.extract("month", PlanillaRow.fecha_acred) == mes,
        func.extract("year", PlanillaRow.fecha_acred) == año,
    ).scalar() or 0

    cartera_cheques = db.query(func.sum(Cheque.monto)).filter(
        Cheque.organizacion_id == org_id,
        Cheque.estado == "pendiente"
    ).scalar() or 0

    return {
        "mes": mes, "año": año,
        "total_cobrado": float(total_cobrado),
        "cheques_en_cartera": float(cartera_cheques),
    }


def _ejecutar_funcion(nombre: str, args: dict, db: Session, org_id: int) -> dict:
    try:
        if nombre == "consultar_pagos_cliente":
            return _consultar_pagos_cliente(db, org_id, **args)
        if nombre == "consultar_cheques":
            return _consultar_cheques(db, org_id, **args)
        if nombre == "consultar_saldo_caja":
            return _consultar_saldo_caja(db, org_id)
        if nombre == "buscar_cliente":
            return _buscar_cliente(db, org_id, **args)
        if nombre == "resumen_financiero":
            return _resumen_financiero(db, org_id, **args)
        return {"error": f"Función desconocida: {nombre}"}
    except Exception as ex:
        logger.warning("Error ejecutando función %s: %s", nombre, ex)
        return {"error": str(ex)}


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("/chat")
def chat(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise HTTPException(503, "Agente no configurado (falta GEMINI_API_KEY en Render)")

    mensaje = str(payload.get("mensaje", "")).strip()
    if not mensaje:
        raise HTTPException(400, "Mensaje vacío")

    org_id = current_user.organizacion_id or 1

    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)

        DECLARACIONES = [
            {
                "name": "consultar_pagos_cliente",
                "description": "Consulta el total pagado por un cliente en planillas conciliadas. Usá cuando pregunten cuánto pagó un cliente, sus pagos o acreditaciones.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cliente_nombre": {"type": "string", "description": "Nombre del cliente (puede ser parcial)"},
                        "desde": {"type": "string", "description": "Fecha desde YYYY-MM-DD (opcional)"},
                        "hasta": {"type": "string", "description": "Fecha hasta YYYY-MM-DD (opcional)"},
                    },
                    "required": ["cliente_nombre"],
                },
            },
            {
                "name": "consultar_cheques",
                "description": "Consulta la cartera de cheques: pendientes, acreditados, rechazados, totales, próximos a vencer.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "estado": {"type": "string", "description": "pendiente, acreditado o rechazado (opcional)"},
                    },
                    "required": [],
                },
            },
            {
                "name": "consultar_saldo_caja",
                "description": "Consulta el saldo de caja del día de hoy: saldo inicial, pagos realizados, saldo disponible.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "buscar_cliente",
                "description": "Busca un cliente por nombre y devuelve sus datos: CBU, CUIT, ID. Usá para verificar datos o autocompletar.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "nombre": {"type": "string", "description": "Nombre parcial o completo del cliente"},
                    },
                    "required": ["nombre"],
                },
            },
            {
                "name": "resumen_financiero",
                "description": "Resumen del mes: total cobrado en planillas y cheques en cartera.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "mes": {"type": "integer", "description": "Número de mes 1-12 (opcional, default mes actual)"},
                        "año": {"type": "integer", "description": "Año (opcional, default año actual)"},
                    },
                    "required": [],
                },
            },
        ]

        hoy = date.today()
        system = (
            f"Sos el asistente financiero de Cuadra, sistema de conciliación bancaria argentino. "
            f"Hoy es {hoy.strftime('%d/%m/%Y')}. "
            f"Respondé siempre en español, de forma concisa y clara. "
            f"Usá formato de pesos argentinos: $1.250.000,00. "
            f"Cuando te pregunten datos financieros, usá las funciones disponibles para consultar la base de datos real. "
            f"Si no encontrás datos, decilo claramente. No inventes números."
        )

        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            tools=[{"function_declarations": DECLARACIONES}],
            system_instruction=system,
        )

        chat_session = model.start_chat()
        response = chat_session.send_message(mensaje)

        # Function calling loop — máximo 3 rondas
        for _ in range(3):
            fn_calls = [
                p for p in response.candidates[0].content.parts
                if hasattr(p, "function_call") and p.function_call.name
            ]
            if not fn_calls:
                break

            fn_responses = []
            for part in fn_calls:
                fc = part.function_call
                result = _ejecutar_funcion(fc.name, dict(fc.args), db, org_id)
                fn_responses.append(
                    genai.protos.Part(
                        function_response=genai.protos.FunctionResponse(
                            name=fc.name,
                            response={"result": result},
                        )
                    )
                )
            response = chat_session.send_message(fn_responses)

        texto = "".join(
            p.text for p in response.candidates[0].content.parts
            if hasattr(p, "text") and p.text
        ).strip()

        return {"respuesta": texto or "No pude generar una respuesta."}

    except Exception as ex:
        logger.warning("Agente error: %s", ex)
        raise HTTPException(500, f"Error del agente: {ex}")

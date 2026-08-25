import os
import base64
import json
import logging
import time
from threading import Lock
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.user import User
from app.middleware.auth import get_current_user
from app.services.tz import hoy_art

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agente", tags=["agente"])

# ── Daily rate limiting (OCR + Chat) ─────────────────────────────────────────
_OCR_DAILY_LIMIT  = int(os.environ.get("OCR_DAILY_LIMIT",  "150"))
_CHAT_DAILY_LIMIT = int(os.environ.get("CHAT_DAILY_LIMIT", "200"))

def _make_counter() -> dict:
    return {"date": None, "count": 0, "lock": Lock()}

_ocr_ctr  = _make_counter()
_chat_ctr = _make_counter()

def _check_limit(ctr: dict, limit: int) -> bool:
    today = hoy_art()
    with ctr["lock"]:
        if ctr["date"] != today:
            ctr["date"] = today
            ctr["count"] = 0
        if ctr["count"] >= limit:
            return False
        ctr["count"] += 1
        return True

def _usage(ctr: dict, limit: int) -> dict:
    today = hoy_art()
    with ctr["lock"]:
        used = ctr["count"] if ctr["date"] == today else 0
    return {"used": used, "limit": limit, "remaining": max(0, limit - used), "date": str(today)}

def _ocr_allowed()  -> bool: return _check_limit(_ocr_ctr,  _OCR_DAILY_LIMIT)
def _chat_allowed() -> bool: return _check_limit(_chat_ctr, _CHAT_DAILY_LIMIT)

_GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


def _classify_gemini_error(ex: Exception) -> tuple[int, str]:
    """Returns (http_status, user_message) for Gemini API exceptions."""
    msg = str(ex).upper()
    if "401" in msg or "403" in msg or "API_KEY_INVALID" in msg or "PERMISSION_DENIED" in msg:
        return 503, "API key de Gemini inválida o sin permisos. Revisá la config en Render."
    if "404" in msg or "NOT_FOUND" in msg:
        return 503, f"Modelo {_GEMINI_MODEL} no disponible. Cambiá GEMINI_MODEL en Render."
    if "RESOURCE_EXHAUSTED" in msg or "429" in str(ex) or "QUOTA" in msg:
        if "PER_DAY" in msg or "DAILY" in msg or "DAY" in msg:
            return 429, "Cuota diaria de Gemini agotada. Disponible mañana a las 21hs 🌙"
        return 429, "Gemini está ocupado. Esperá 1 minuto y volvé a intentar ⏱️"
    return 500, "El asistente no está disponible en este momento. Intentá de nuevo."


def _gemini_send(session, message, retries: int = 1) -> object:
    """Send a message with one retry on transient 429 (per-minute limit)."""
    for attempt in range(retries + 1):
        try:
            return session.send_message(message)
        except Exception as ex:
            msg = str(ex).upper()
            is_transient = "RESOURCE_EXHAUSTED" in msg or "429" in str(ex)
            if is_transient and attempt < retries:
                time.sleep(5)
                continue
            raise

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

    base = db.query(Cheque).filter(Cheque.organizacion_id == org_id)
    if estado:
        base = base.filter(Cheque.estado == estado)

    # Agregados via SQL (GROUP BY) en vez de cargar todas las filas a Python.
    agregados = (
        base.with_entities(
            Cheque.estado,
            func.count(Cheque.id),
            func.coalesce(func.sum(Cheque.monto), 0),
        )
        .group_by(Cheque.estado)
        .all()
    )
    por_estado = {
        est: {"cantidad": cant, "total": float(total)}
        for est, cant, total in agregados
    }
    total_cheques = sum(v["cantidad"] for v in por_estado.values())
    total_monto = sum(v["total"] for v in por_estado.values())

    from app.services.reportes_service import CHEQUE_EN_CARTERA
    proximos_rows = (
        base.filter(Cheque.estado.in_(CHEQUE_EN_CARTERA))
        .order_by(Cheque.fecha_deposito.asc().nullslast())
        .limit(5)
        .all()
    )
    proximos = [
        {"numero": c.numero, "monto": float(c.monto or 0), "cliente": c.cliente_nombre,
         "vencimiento": str(c.fecha_deposito), "banco": c.banco_origen}
        for c in proximos_rows
    ]
    return {
        "total_cheques": total_cheques,
        "total_monto": total_monto,
        "por_estado": por_estado,
        "proximos_a_vencer": proximos,
    }


def _consultar_saldo_caja(db, org_id):
    from app.models.caja import ArqueoDiario

    arqueo = db.query(ArqueoDiario).filter(
        ArqueoDiario.organizacion_id == org_id,
        ArqueoDiario.fecha == hoy_art()
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

    hoy = hoy_art()
    mes = int(mes) if mes else hoy.month
    año = int(año) if año else hoy.year

    total_cobrado = db.query(func.sum(PlanillaRow.monto)).join(Planilla).filter(
        Planilla.organizacion_id == org_id,
        PlanillaRow.status == "ok",
        Planilla.deleted_at.is_(None),
        func.extract("month", PlanillaRow.fecha_acred) == mes,
        func.extract("year", PlanillaRow.fecha_acred) == año,
    ).scalar() or 0

    from app.services.reportes_service import CHEQUE_EN_CARTERA
    cartera_cheques = db.query(func.sum(Cheque.monto)).filter(
        Cheque.organizacion_id == org_id,
        Cheque.estado.in_(CHEQUE_EN_CARTERA),
    ).scalar() or 0

    return {
        "mes": mes, "año": año,
        "total_cobrado": float(total_cobrado),
        "cheques_en_cartera": float(cartera_cheques),
    }


def _consultar_alertas(db, org_id):
    """Alertas operativas vigentes: cheques por vencer/vencidos, filas atrasadas,
    movimientos sin asignar, planillas con descuadre de total y filas ambiguas
    por revisar. Misma fuente que la campana del Dashboard."""
    from app.services import reportes_service as svc
    return svc.calcular_alertas(db, org_id)


def _explicar_filas_pendientes(db, org_id, cliente_nombre=None, limit=10):
    """Trae filas de planilla que NO conciliaron (status != ok) para explicar
    por qué, con el dato real de motivo/comentario que dejó el motor de conciliación."""
    from app.models.planilla import Planilla, PlanillaRow
    from app.models.cliente import Cliente

    limit = min(int(limit or 10), 25)
    q = (
        db.query(PlanillaRow, Planilla, Cliente)
        .join(Planilla, PlanillaRow.planilla_id == Planilla.id)
        .outerjoin(Cliente, Planilla.cliente_id == Cliente.id)
        .filter(
            Planilla.organizacion_id == org_id,
            Planilla.deleted_at.is_(None),
            PlanillaRow.status != "ok",
        )
    )
    if cliente_nombre:
        q = q.filter(Cliente.nombre.ilike(f"%{cliente_nombre}%"))
    filas = q.order_by(PlanillaRow.id.desc()).limit(limit).all()

    if not filas:
        return {"filas": [], "mensaje": "No hay filas pendientes que coincidan con ese criterio."}

    return {"filas": [
        {
            "cliente": cli.nombre if cli else None,
            "planilla": pl.nombre_archivo,
            "monto": float(row.monto),
            "status": row.status,
            "cuit": row.cuit,
            "titular": row.titular,
            "fecha_acred_esperada": str(row.fecha_acred) if row.fecha_acred else None,
            "comentario": row.comentario_revision,
        }
        for row, pl, cli in filas
    ]}


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
        if nombre == "consultar_alertas":
            return _consultar_alertas(db, org_id)
        if nombre == "explicar_filas_pendientes":
            return _explicar_filas_pendientes(db, org_id, **args)
        return {"error": f"Función desconocida: {nombre}"}
    except Exception as ex:
        logger.warning("Error ejecutando función %s: %s", nombre, ex)
        return {"error": str(ex)}


# ── Lógica compartida de chat (la usan /chat y /saludo-proactivo) ───────────────

def _run_chat_message(mensaje: str, db: Session, org_id: int, api_key: str) -> str:
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
        {
            "name": "consultar_alertas",
            "description": "Trae las alertas operativas vigentes: cheques por vencer en 7 días, cheques vencidos, filas de planilla atrasadas +30 días, movimientos bancarios sin asignar en los últimos 30 días, planillas cuyo total declarado por el cliente no cuadra con la suma de sus filas, y filas de planilla marcadas como 'ambiguo' (varios candidatos de conciliación con el mismo puntaje) pendientes de elegir a mano. Usala proactivamente al saludar o cuando preguntan 'qué necesito ver hoy' / 'hay algo importante' / 'cómo viene todo'.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "explicar_filas_pendientes",
            "description": "Trae filas de planilla que NO conciliaron (status distinto de 'ok') con el motivo real registrado por el motor de conciliación (no está / duplicado / faltan datos / en revisión) para poder EXPLICAR por qué un pago de un cliente no quedó conciliado. Usala cuando preguntan 'por qué no concilió X' o 'qué falta de la planilla de X'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cliente_nombre": {"type": "string", "description": "Nombre del cliente para filtrar (opcional, parcial)"},
                    "limit": {"type": "integer", "description": "Máximo de filas a traer (opcional, default 10, máximo 25)"},
                },
                "required": [],
            },
        },
    ]

    hoy = hoy_art()
    system = (
        f"Sos el asistente financiero de Cuadra, sistema de conciliación bancaria y contable argentino. "
        f"Hoy es {hoy.strftime('%d/%m/%Y')}. "
        f"Respondé siempre en español, conciso pero NUNCA solo un número pelado: "
        f"cuando das un dato, agregá una línea de contexto o interpretación (¿es bueno, malo, normal? ¿hay algo "
        f"que requiera acción?). Sos un asistente PROACTIVO Y EXPLICATIVO, no un buscador de datos: "
        f"- Si te preguntan 'cómo viene todo', 'hay algo importante' o un saludo genérico, consultá alertas y "
        f"  resumen financiero y contestá con lo más urgente primero, sugiriendo una acción concreta. "
        f"- Si te preguntan por qué algo no conciliá o por qué falta un pago, usá explicar_filas_pendientes y "
        f"  traducí el motivo técnico a lenguaje simple (ej. 'no está' significa que no encontramos ningún "
        f"  movimiento bancario con ese monto en el período; 'duplicado' significa que el monto coincide con "
        f"  más de un movimiento y no se puede saber cuál es sin más datos como CUIT o titular). "
        f"- Si detectás algo que valga la pena avisar sin que lo pidan explícitamente (ej. cheques vencidos, "
        f"  movimientos viejos sin asignar), mencionalo aunque la pregunta haya sido otra cosa. "
        f"Usá formato de pesos argentinos: $1.250.000,00. "
        f"Usá las funciones disponibles para consultar la base de datos real — nunca inventes números. "
        f"Si no encontrás datos, decilo claramente."
    )

    model = genai.GenerativeModel(
        model_name=_GEMINI_MODEL,
        tools=[{"function_declarations": DECLARACIONES}],
        system_instruction=system,
    )

    chat_session = model.start_chat()
    response = _gemini_send(chat_session, mensaje)

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
        response = _gemini_send(chat_session, fn_responses)

    texto = "".join(
        p.text for p in response.candidates[0].content.parts
        if hasattr(p, "text") and p.text
    ).strip()

    return texto or "No pude generar una respuesta."


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/chat")
def chat(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _chat_allowed():
        raise HTTPException(429, "Límite diario del asistente IA alcanzado. Volvé mañana 🙂")

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(503, "Agente no configurado (falta GEMINI_API_KEY en Render)")

    mensaje = str(payload.get("mensaje", "")).strip()
    if not mensaje:
        raise HTTPException(400, "Mensaje vacío")

    org_id = current_user.organizacion_id or 1

    try:
        texto = _run_chat_message(mensaje, db, org_id, api_key)
        return {"respuesta": texto}
    except Exception as ex:
        logger.warning("Agente chat error: %s", ex)
        status, msg = _classify_gemini_error(ex)
        raise HTTPException(status, msg)


@router.get("/saludo-proactivo")
def saludo_proactivo(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Genera un saludo proactivo al abrir el chat: revisa alertas + resumen
    financiero y devuelve 2-4 frases con lo más relevante de hoy, sin que el
    usuario tenga que preguntar nada. Mismo cupo diario que /chat."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(503, "Agente no configurado (falta GEMINI_API_KEY en Render)")
    if not _chat_allowed():
        raise HTTPException(429, "Límite diario del asistente IA alcanzado. Volvé mañana 🙂")

    org_id = current_user.organizacion_id or 1
    mensaje_interno = (
        "Dame un pantallazo proactivo de hoy: revisá las alertas vigentes y el resumen "
        "financiero del mes, y contame en 2 a 4 frases qué es lo más importante que tengo "
        "que saber ahora, sugiriendo una acción concreta si corresponde. Si no hay nada "
        "urgente decilo de forma breve y positiva. No me preguntes nada, contame directamente."
    )

    try:
        texto = _run_chat_message(mensaje_interno, db, org_id, api_key)
        return {"respuesta": texto}
    except Exception as ex:
        logger.warning("Agente saludo proactivo error: %s", ex)
        status, msg = _classify_gemini_error(ex)
        raise HTTPException(status, msg)


# ── OCR helpers ───────────────────────────────────────────────────────────────

def _parse_b64_image(imagen_b64: str) -> tuple[str, bytes]:
    """Returns (mime_type, raw_bytes) from a data-URL or raw base64 string."""
    if "," in imagen_b64:
        header, data = imagen_b64.split(",", 1)
        mime_type = header.split(":")[1].split(";")[0] if ":" in header else "image/jpeg"
    else:
        data = imagen_b64
        mime_type = "image/jpeg"
    return mime_type, base64.b64decode(data)


def _call_gemini_ocr(api_key: str, mime_type: str, raw_bytes: bytes, prompt: str) -> dict:
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(_GEMINI_MODEL)
    image_part = genai.protos.Part(
        inline_data=genai.protos.Blob(mime_type=mime_type, data=raw_bytes)
    )
    response = model.generate_content([image_part, prompt])
    try:
        texto = response.text.strip()
    except Exception:
        return {}  # safety block o respuesta sin texto
    if not texto:
        return {}
    # Strip markdown code fences if present
    if texto.startswith("```"):
        lines = texto.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        texto = "\n".join(lines).strip()
    return json.loads(texto)


@router.post("/ocr-cheque")
def ocr_cheque(
    payload: dict,
    current_user: User = Depends(get_current_user),
):
    if not _ocr_allowed():
        raise HTTPException(429, "Límite diario de OCR alcanzado")
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(503, "OCR no configurado (falta GEMINI_API_KEY)")

    imagen_b64 = str(payload.get("imagen_base64", "")).strip()
    if not imagen_b64:
        raise HTTPException(400, "Imagen vacía")

    try:
        mime_type, raw_bytes = _parse_b64_image(imagen_b64)
        prompt = (
            "Extraé los datos de este cheque bancario argentino. "
            "Respondé SOLO con un JSON válido (sin texto extra, sin markdown), con estos campos "
            "(usá null si no está visible o no podés leerlo): "
            '{"numero": "string o null", "banco_origen": "string o null", "librador": "string o null", '
            '"monto": número_sin_formato_o_null, "fecha_emision": "YYYY-MM-DD o null", '
            '"fecha_deposito": "YYYY-MM-DD o null"}'
        )
        datos = _call_gemini_ocr(api_key, mime_type, raw_bytes, prompt)
        return datos
    except json.JSONDecodeError:
        return {}
    except Exception as ex:
        logger.warning("OCR cheque error: %s", ex)
        _, msg = _classify_gemini_error(ex)
        raise HTTPException(500, msg)


@router.post("/ocr-transferencia")
def ocr_transferencia(
    payload: dict,
    current_user: User = Depends(get_current_user),
):
    if not _ocr_allowed():
        raise HTTPException(429, "Límite diario de OCR alcanzado")
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(503, "OCR no configurado (falta GEMINI_API_KEY)")

    imagen_b64 = str(payload.get("imagen_base64", "")).strip()
    if not imagen_b64:
        raise HTTPException(400, "Imagen vacía")

    try:
        mime_type, raw_bytes = _parse_b64_image(imagen_b64)
        prompt = (
            "Extraé los datos de este comprobante de transferencia bancaria argentina. "
            "Respondé SOLO con un JSON válido (sin texto extra, sin markdown). "
            "Para el monto: devolvé SOLO el número decimal puro, sin $, sin puntos de miles, sin comas de miles. "
            "Usá punto como separador decimal. Ejemplo: si ves '$15.000,50' devolvé 15000.50, si ves '$ 1.200.000' devolvé 1200000. "
            "Si un campo no está visible o no podés leerlo, devolvé null. "
            'Campos: {"monto": numero_o_null, "fecha": "YYYY-MM-DD o null", '
            '"beneficiario": "nombre del destinatario o null", '
            '"referencia": "número de operación/CVU/alias o null"}'
        )
        datos = _call_gemini_ocr(api_key, mime_type, raw_bytes, prompt)
        return datos
    except json.JSONDecodeError:
        return {}
    except Exception as ex:
        logger.warning("OCR transferencia error: %s", ex)
        _, msg = _classify_gemini_error(ex)
        raise HTTPException(500, msg)


def _glosario_transcripcion(db: Session, org_id: int) -> str:
    """Nombres de clientes de la org, para que Gemini no los transcriba mal (son nombres propios)."""
    from app.models.cliente import Cliente
    nombres = [
        n for (n,) in db.query(Cliente.nombre)
        .filter(Cliente.organizacion_id == org_id, Cliente.deleted_at.is_(None))
        .order_by(Cliente.nombre)
        .limit(200)
        .all()
    ]
    return ", ".join(nombres)


@router.post("/transcribir")
async def transcribir_audio(
    audio: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Transcribe un audio (webm/mp4/etc) a texto con Gemini. Devuelve {texto}."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(503, "Transcripción no configurada (falta GEMINI_API_KEY)")

    raw = await audio.read()
    if not raw:
        raise HTTPException(400, "Audio vacío")
    mime = audio.content_type or "audio/webm"

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name=_GEMINI_MODEL)
        org_id = current_user.organizacion_id or 1
        clientes = _glosario_transcripcion(db, org_id)
        contexto_clientes = (
            f" Nombres de clientes que pueden mencionarse (para no transcribirlos mal): {clientes}."
            if clientes else ""
        )
        prompt = (
            "Transcribí este audio en español rioplatense. Es una consulta sobre un sistema de "
            "conciliación bancaria y contabilidad: pueden aparecer términos como CUIT, CBU, cheque, "
            "planilla, conciliación, extracto, liquidación, comisión, IIBB, IVA, monotributo, sueldo."
            + contexto_clientes +
            " Devolvé únicamente el texto exacto de lo que se dice, sin comillas ni comentarios."
        )
        audio_part = genai.protos.Part(
            inline_data=genai.protos.Blob(mime_type=mime, data=raw)
        )
        response = model.generate_content([audio_part, prompt])
        texto = (response.text or "").strip()
        return {"texto": texto}
    except Exception as ex:
        logger.warning("Transcripción audio error: %s", ex)
        status, msg = _classify_gemini_error(ex)
        raise HTTPException(status, msg)


@router.get("/ocr-usage")
def get_ocr_usage(current_user: User = Depends(get_current_user)):
    return {
        "ocr":  _usage(_ocr_ctr,  _OCR_DAILY_LIMIT),
        "chat": _usage(_chat_ctr, _CHAT_DAILY_LIMIT),
    }

"""
Guarda planillas conciliadas en la estructura de carpetas:
  Desktop/clientes/{Cliente}/{Mes Año}/{archivo}_acreditado.xlsx

Solo funciona cuando el backend corre en la PC local.
En produccion (Render) simplemente devuelve el archivo para descargar.
"""

import os
import platform
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
import io

from app.database import get_db
from app.models.planilla import Planilla
from app.models.extracto import MovimientoBanco
from app.models.user import User
from app.middleware.auth import get_current_user
from app.services.excel_export import export_planilla_conciliada
from sqlalchemy.orm import Session

router = APIRouter(prefix="/clientes", tags=["clientes"])

CLIENTES_NOMBRES = [
    "Green", "Tucu", "David", "Smt", "Gwinn",
    "Innova", "Camparo", "Alojando", "Pinares", "Paraguay"
]


def get_desktop_path() -> str:
    """Ruta al Desktop según el OS"""
    if platform.system() == "Windows":
        return os.path.join(os.path.expanduser("~"), "Desktop")
    return os.path.expanduser("~/Desktop")


def get_clientes_base() -> str:
    return os.path.join(get_desktop_path(), "clientes")


def is_local() -> bool:
    """True si estamos corriendo en la PC local (no en Render/cloud)"""
    return not os.getenv("RENDER") and not os.getenv("RAILWAY_ENVIRONMENT")


@router.post("/planillas/{planilla_id}/guardar")
def guardar_planilla_en_carpeta(
    planilla_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user)
):
    """
    Guarda el archivo conciliado en Desktop/clientes/{Cliente}/{Mes Año}/
    y también lo devuelve para descargar.
    """
    p = db.query(Planilla).filter(Planilla.id == planilla_id).first()
    if not p:
        raise HTTPException(404, "Planilla no encontrada")

    # Enriquecer rows con datos del movimiento
    mov_ids = [r.orden_movimiento_acreditado for r in p.rows if r.orden_movimiento_acreditado]
    movs_map = {m.id: m for m in db.query(MovimientoBanco).filter(MovimientoBanco.id.in_(mov_ids)).all()} if mov_ids else {}

    rows_data, movimientos_acreditados, ids_vistos = [], [], set()
    for r in p.rows:
        mov = movs_map.get(r.orden_movimiento_acreditado) if r.orden_movimiento_acreditado else None
        rows_data.append({
            "monto": r.monto, "cuit": r.cuit, "titular": r.titular, "status": r.status,
            "orden_movimiento_acreditado": r.orden_movimiento_acreditado,
            "mov_titular": mov.titular if mov else None,
            "mov_fecha": mov.fecha if mov else None,
            "mov_fecha_acred": mov.fecha_acred if mov else None,
        })
        if mov and mov.id not in ids_vistos:
            ids_vistos.add(mov.id)
            movimientos_acreditados.append({
                "orden": mov.orden, "fecha": mov.fecha, "mes": mov.mes,
                "titular": mov.titular, "monto": mov.monto, "saldo": mov.saldo,
                "cliente_acreditado": mov.cliente_acreditado, "fecha_acred": mov.fecha_acred,
            })

    planilla_data = {"cliente_nombre": p.cliente.nombre, "nombre_archivo": p.nombre_archivo, "rows": rows_data}
    xlsx = export_planilla_conciliada(planilla_data, movimientos_acreditados)

    # Nombre del archivo
    nombre_base = p.nombre_archivo.replace('.xlsx', '').replace('.XLSX', '')
    fecha_hoy = datetime.now()
    nombre_archivo = f"{nombre_base}_acreditado_{fecha_hoy.strftime('%d.%m')}.xlsx"

    saved_path = None

    # Guardar en carpeta local si estamos en la PC
    if is_local():
        try:
            # Nombre del mes en español
            MESES = ['Enero','Febrero','Marzo','Abril','Mayo','Junio',
                     'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']
            mes_anio = f"{MESES[fecha_hoy.month - 1]} {fecha_hoy.year}"

            anio = str(fecha_hoy.year)
            carpeta = os.path.join(get_clientes_base(), p.cliente.nombre, anio, mes_anio)
            os.makedirs(carpeta, exist_ok=True)

            # Nombre: "Green acreditado 02-05-2026.xlsx"
            nombre_archivo = f"{p.cliente.nombre} acreditado {fecha_hoy.strftime('%d-%m-%Y')}.xlsx"
            ruta_final = os.path.join(carpeta, nombre_archivo)
            # Si ya existe, agregar sufijo (2), (3), etc.
            contador = 2
            while os.path.exists(ruta_final):
                nombre_con_sufijo = f"{nombre_base}_acreditado_{fecha_hoy.strftime('%d.%m')} ({contador}).xlsx"
                ruta_final = os.path.join(carpeta, nombre_con_sufijo)
                nombre_archivo = nombre_con_sufijo
                contador += 1

            with open(ruta_final, 'wb') as f:
                f.write(xlsx)
            saved_path = ruta_final
            print(f"[clientes] Guardado en: {ruta_final}")
        except Exception as e:
            print(f"[clientes] Warning al guardar: {e}")

    headers = {"Content-Disposition": f'attachment; filename="{nombre_archivo}"'}
    if saved_path:
        headers["X-Saved-Path"] = saved_path

    return StreamingResponse(
        io.BytesIO(xlsx),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers
    )


@router.get("/estructura")
def get_estructura(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return {"clientes": CLIENTES_NOMBRES}


@router.get("/archivos")
def get_archivos_por_cliente(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """
    Devuelve archivos conciliados agrupados por cliente y mes.
    Usa agregación SQL en vez de cargar todos los rows a memoria.
    """
    from app.models.planilla import Planilla, PlanillaRow
    from app.models.cliente import Cliente
    from sqlalchemy import func, case
    from collections import defaultdict

    MESES = ['Enero','Febrero','Marzo','Abril','Mayo','Junio',
             'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']

    rows = (
        db.query(
            Cliente.nombre,
            Planilla.id,
            Planilla.nombre_archivo,
            Planilla.fecha_carga,
            func.count(PlanillaRow.id).label("total"),
            func.sum(case((PlanillaRow.status == "ok", 1), else_=0)).label("acreditadas"),
        )
        .join(Cliente, Planilla.cliente_id == Cliente.id)
        .outerjoin(PlanillaRow, PlanillaRow.planilla_id == Planilla.id)
        .group_by(Cliente.nombre, Planilla.id, Planilla.nombre_archivo, Planilla.fecha_carga)
        .order_by(Planilla.fecha_carga.desc())
        .all()
    )

    resultado: dict = defaultdict(lambda: defaultdict(list))
    for cliente_nombre, p_id, nombre_archivo, fecha_carga, total, acreditadas in rows:
        anio_str = str(fecha_carga.year)
        mes_anio = MESES[fecha_carga.month - 1]
        resultado[cliente_nombre][f"{anio_str}/{mes_anio}"].append({
            "id": p_id,
            "nombre_archivo": nombre_archivo,
            "fecha_carga": fecha_carga.isoformat(),
            "total": int(total or 0),
            "acreditadas": int(acreditadas or 0),
        })

    clientes_lista = []
    for cliente_nombre in sorted(resultado.keys()):
        meses = []
        for mes_nombre, archivos in resultado[cliente_nombre].items():
            meses.append({"mes": mes_nombre, "archivos": archivos})
        clientes_lista.append({"nombre": cliente_nombre, "meses": meses})

    return {"clientes": clientes_lista}

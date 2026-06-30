"""
Guarda planillas conciliadas en la estructura de carpetas:
  Desktop/clientes/{Cliente}/{Mes Año}/{archivo}_acreditado.xlsx

Solo funciona cuando el backend corre en la PC local.
En produccion (Render) simplemente devuelve el archivo para descargar.
"""

import logging
import os

logger = logging.getLogger(__name__)
import platform
from datetime import datetime
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from typing import Optional
import io

from app.database import get_db
from app.models.planilla import Planilla
from app.models.extracto import MovimientoBanco
from app.models.user import User
from app.middleware.auth import get_current_user, require_permission, can_switch_org
from app.services.excel_export import export_planilla_conciliada
from app.services.tz import hoy_art, now_art
from sqlalchemy.orm import Session
from sqlalchemy import func, case

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

    # Fallback: para filas "ok" sin FK al movimiento (link roto), buscar por monto + cliente en el extracto
    fallback_map: dict = {}  # monto (float) -> MovimientoBanco (primer candidato libre)
    ok_sin_link = [r for r in p.rows if r.status == "ok" and not r.orden_movimiento_acreditado]
    if ok_sin_link and p.extracto_id:
        ya_usados = set(movs_map.keys())
        candidatos = (
            db.query(MovimientoBanco)
            .filter(
                MovimientoBanco.extracto_id == p.extracto_id,
                MovimientoBanco.cliente_acreditado == p.cliente.nombre,
            )
            .order_by(MovimientoBanco.orden)
            .all()
        )
        for c in candidatos:
            if c.id not in ya_usados:
                key = float(c.monto) if c.monto is not None else None
                if key is not None and key not in fallback_map:
                    fallback_map[key] = c
                    ya_usados.add(c.id)

    rows_data, movimientos_acreditados, ids_vistos = [], [], set()
    for r in p.rows:
        mov = movs_map.get(r.orden_movimiento_acreditado) if r.orden_movimiento_acreditado else None
        # Fallback: si ok pero sin link, intentar por monto
        if mov is None and r.status == "ok":
            monto_key = float(r.monto) if r.monto is not None else None
            mov = fallback_map.get(monto_key) if monto_key is not None else None
        fecha_acred_fallback = r.fecha_acred  # la fila siempre guarda esto cuando se concilia
        rows_data.append({
            "monto": r.monto, "cuit": r.cuit, "titular": r.titular, "status": r.status,
            "orden_movimiento_acreditado": mov.orden if mov else None,
            "mov_titular": mov.titular if mov else None,
            "mov_fecha": mov.fecha if mov else None,
            "mov_fecha_acred": (mov.fecha_acred if mov else None) or fecha_acred_fallback,
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

    # Nombre: "{cliente} acreditado {d.m}.xlsx" — usa la fecha mas reciente de acreditacion
    fechas_acred = [mov.fecha_acred for mov in movs_map.values() if mov.fecha_acred]
    fecha_hoy = now_art()
    fecha_ref = max(fechas_acred) if fechas_acred else fecha_hoy.date()
    cliente_slug = (p.cliente.nombre or "cliente").strip().lower()
    nombre_archivo = f"{cliente_slug} acreditado {fecha_ref.day}.{fecha_ref.month}.xlsx"

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

            # Nombre coincide con el de descarga: "alojando acreditado 8.5.xlsx"
            ruta_final = os.path.join(carpeta, nombre_archivo)
            contador = 2
            while os.path.exists(ruta_final):
                base_sin_ext = nombre_archivo[:-5]  # quita ".xlsx"
                nombre_con_sufijo = f"{base_sin_ext} ({contador}).xlsx"
                ruta_final = os.path.join(carpeta, nombre_con_sufijo)
                nombre_archivo = nombre_con_sufijo
                contador += 1

            with open(ruta_final, 'wb') as f:
                f.write(xlsx)
            saved_path = ruta_final
            logger.info("Guardado en: %s", ruta_final)
        except Exception as e:
            logger.warning("Error guardando planilla local: %s", e)

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
def get_archivos_por_cliente(
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Devuelve archivos conciliados agrupados por:
      organizacion -> cliente -> año/mes -> [archivos]

    Incluye TODOS los clientes (aunque no tengan planillas todavia) para que
    aparezcan como carpetas vacias en la vista, listas para recibir archivos.
    """
    from app.models.planilla import Planilla
    from app.models.cliente import Cliente
    from app.models.organizacion import Organizacion
    from collections import defaultdict

    MESES = ['Enero','Febrero','Marzo','Abril','Mayo','Junio',
             'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']

    # Scope por org segun rol
    orgs_q = db.query(Organizacion)
    if can_switch_org(current_user, org_id) and org_id:
        orgs_q = orgs_q.filter(Organizacion.id == org_id)
    elif not current_user.is_superadmin:
        orgs_q = orgs_q.filter(Organizacion.id == (current_user.organizacion_id or 1))
    orgs = orgs_q.order_by(Organizacion.id).all()

    # Indexar planillas por org_id -> cliente_id -> "anio/mes"
    # Solo planillas activas (no soft-deleted) para evitar N+1 con filas de planillas borradas
    from app.models.planilla import PlanillaRow
    pq = db.query(Planilla).join(Cliente).filter(Planilla.deleted_at.is_(None))
    if can_switch_org(current_user, org_id) and org_id:
        pq = pq.filter(Planilla.organizacion_id == org_id)
    elif not current_user.is_superadmin:
        pq = pq.filter(Planilla.organizacion_id == (current_user.organizacion_id or 1))
    planillas = pq.order_by(Planilla.fecha_carga.desc()).all()

    # Precompute total y acreditadas por planilla en una sola query (evita N+1)
    counts_map: dict = {}
    if planillas:
        pl_ids = [p.id for p in planillas]
        rows_agg = db.query(
            PlanillaRow.planilla_id,
            func.count(PlanillaRow.id).label("total"),
            func.sum(case((PlanillaRow.status == "ok", 1), else_=0)).label("acreditadas"),
        ).filter(PlanillaRow.planilla_id.in_(pl_ids)).group_by(PlanillaRow.planilla_id).all()
        counts_map = {r.planilla_id: (int(r.total), int(r.acreditadas or 0)) for r in rows_agg}

    archivos_idx: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for p in planillas:
        total, acreditadas = counts_map.get(p.id, (0, 0))
        p_org_id = p.organizacion_id or 1
        anio_str = str(p.fecha_carga.year)
        mes_nombre = MESES[p.fecha_carga.month - 1]
        archivos_idx[p_org_id][p.cliente_id][f"{anio_str}/{mes_nombre}"].append({
            "id": p.id,
            "nombre_archivo": p.nombre_archivo,
            "fecha_carga": p.fecha_carga.isoformat(),
            "fecha_dia": p.fecha_carga.strftime("%d/%m"),
            "total": total,
            "acreditadas": acreditadas,
        })

    # Construir respuesta jerarquica
    resultado_orgs = []
    for org in orgs:
        # Clientes de esta org
        cli_q = db.query(Cliente).filter(Cliente.organizacion_id == org.id).order_by(Cliente.nombre)
        clientes_org = cli_q.all()

        clientes_lista = []
        for c in clientes_org:
            meses_dict = archivos_idx.get(org.id, {}).get(c.id, {})
            meses = [{"mes": mes, "archivos": archivos}
                     for mes, archivos in sorted(meses_dict.items(), reverse=True)]
            total_archivos = sum(len(a["archivos"]) for a in meses)
            clientes_lista.append({
                "id": c.id,
                "nombre": c.nombre,
                "cuit": c.cuit,
                "porcentaje_comision": float(c.porcentaje_comision) if c.porcentaje_comision is not None else None,
                "porcentaje_comision_local": float(c.porcentaje_comision_local) if c.porcentaje_comision_local is not None else None,
                "porcentaje_comision_interior": float(c.porcentaje_comision_interior) if c.porcentaje_comision_interior is not None else None,
                "total_archivos": total_archivos,
                "meses": meses,
            })

        resultado_orgs.append({
            "id": org.id,
            "nombre": org.nombre,
            "total_clientes": len(clientes_lista),
            "clientes": clientes_lista,
        })

    # Compatibilidad con frontend viejo (PWA cacheada con SW anterior):
    # devolvemos tambien la lista plana de clientes con la misma forma de antes,
    # para que el codigo legacy no muestre vacio mientras el SW se actualiza.
    clientes_planos = []
    for org in resultado_orgs:
        for c in org["clientes"]:
            if c["meses"]:
                clientes_planos.append({"nombre": c["nombre"], "meses": c["meses"]})

    return {
        "organizaciones": resultado_orgs,
        "clientes": clientes_planos,
    }


@router.post("/{cliente_id}/buscar-movimiento")
def buscar_movimiento_para_acreditar(
    cliente_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Busca movimientos del extracto que podrian corresponder a un comprobante
    de pago (Mercado Pago, Cuenta DNI, foto, etc).

    Payload:
      - monto: float (obligatorio)
      - fecha: ISO date (obligatorio) — fecha del comprobante
      - tolerancia_dias: int = 5 — ventana de busqueda
      - referencia: str opcional — codigo de ref (ej "00194624")
      - origen: str opcional — nombre/CUIT del que paga (ej "Walter Daniel Leguisa" o "20221499")

    Devuelve lista de candidatos ordenados por score, donde el primero suele
    ser el correcto. Si hay uno solo de score alto, el frontend lo acredita
    directo. Si hay varios, muestra la lista.
    """
    import re
    from datetime import timedelta
    from app.models.cliente import Cliente

    q = db.query(Cliente).filter(Cliente.id == cliente_id)
    if not current_user.is_superadmin:
        q = q.filter(Cliente.organizacion_id == current_user.organizacion_id)
    cli = q.first()
    if not cli:
        raise HTTPException(404, "Cliente no encontrado")

    # Todos los campos son opcionales individualmente, pero al menos UNO debe venir.
    monto = None
    try:
        m_raw = payload.get("monto")
        if m_raw is not None and str(m_raw).strip() != "":
            monto = Decimal(str(m_raw))
            if monto <= 0:
                monto = None
    except (TypeError, ValueError):
        monto = None

    fecha_ref = None
    fecha_s = (payload.get("fecha") or "").strip()
    if fecha_s:
        try:
            fecha_ref = datetime.fromisoformat(fecha_s).date() if "-" in fecha_s else \
                        datetime.strptime(fecha_s, "%d/%m/%Y").date()
        except ValueError:
            raise HTTPException(400, "fecha invalida (usar YYYY-MM-DD o DD/MM/YYYY)")

    tolerancia = int(payload.get("tolerancia_dias") or 5)
    referencia = (payload.get("referencia") or "").strip()
    origen = (payload.get("origen") or "").strip().lower()
    ref_norm = re.sub(r"\D", "", referencia).lstrip("0") if referencia else ""

    if not any([monto, fecha_ref, ref_norm, origen]):
        raise HTTPException(400, "ingresa al menos uno: monto, fecha, referencia u origen")

    # Construir query progresivamente con los filtros que SI vinieron
    q = db.query(MovimientoBanco)
    if monto is not None:
        q = q.filter(MovimientoBanco.monto >= monto - 0.01,
                     MovimientoBanco.monto <= monto + 0.01)
    if fecha_ref is not None:
        desde = fecha_ref - timedelta(days=tolerancia)
        hasta = fecha_ref + timedelta(days=tolerancia)
        q = q.filter(MovimientoBanco.fecha >= desde,
                     MovimientoBanco.fecha <= hasta)
    if not current_user.is_superadmin:
        q = q.filter(MovimientoBanco.organizacion_id == (current_user.organizacion_id or 1))

    # Si no vino monto ni fecha, limitamos a 500 movs y filtramos en Python por
    # ref/origen (evita traer todo el extracto a memoria).
    movs = q.limit(2000).all() if (monto is None and fecha_ref is None) else q.all()

    candidatos = []
    for m in movs:
        score = 0
        razones = []

        # Diferencia fecha (mas cerca = mejor) solo si vino fecha
        if fecha_ref is not None:
            dias = abs((m.fecha - fecha_ref).days) if m.fecha else 99
            score += max(0, 10 - dias * 2)
            if dias == 0: razones.append("fecha exacta")
            elif dias <= 2: razones.append(f"fecha ±{dias}d")

        titular_lower = (m.titular or "").lower()

        # Match referencia (alto valor — el codigo de ref del comprobante suele
        # estar en el titular o concepto)
        if ref_norm and ref_norm in re.sub(r"\D", "", titular_lower):
            score += 15
            razones.append(f"ref {ref_norm}")

        # Match origen (nombre o CUIT)
        if origen:
            origen_solo_dig = re.sub(r"\D", "", origen)
            if origen_solo_dig and len(origen_solo_dig) >= 6 and origen_solo_dig in re.sub(r"\D", "", titular_lower):
                score += 12
                razones.append("CUIT/DNI match")
            # Match palabras del nombre
            palabras = [p for p in re.findall(r"[a-z]{3,}", origen) if p not in ("del", "de", "la", "los")]
            matches_palabras = sum(1 for p in palabras if p in titular_lower)
            if matches_palabras >= 1:
                score += 4 * matches_palabras
                razones.append(f"{matches_palabras} palabra(s) del origen")

        # Penalizar movs ya acreditados a OTRO cliente
        ya_acreditado_a_otro = (m.cliente_acreditado and m.cliente_acreditado != cli.nombre
                                and m.cliente_acreditado.lower() != "no identificado")
        if ya_acreditado_a_otro:
            score -= 100  # baja al fondo pero todavia es visible para que ella decida

        # Si ya esta acreditado a ESTE cliente, marcar
        ya_este = m.cliente_acreditado and m.cliente_acreditado.lower() == cli.nombre.lower()

        # Si solo se busco por ref/origen (sin monto ni fecha), descartar candidatos
        # con score == 0 (no matchearon nada salvo el filtro vacio)
        if score <= 0 and monto is None and fecha_ref is None and not ya_este:
            continue

        candidatos.append({
            "id": m.id,
            "extracto_id": m.extracto_id,
            "orden": m.orden,
            "fecha": m.fecha.isoformat() if m.fecha else None,
            "titular": m.titular,
            "monto": m.monto,
            "saldo": m.saldo,
            "cliente_acreditado": m.cliente_acreditado,
            "ya_acreditado_a_este_cliente": ya_este,
            "ya_acreditado_a_otro": ya_acreditado_a_otro,
            "score": score,
            "razones": razones,
        })

    candidatos.sort(key=lambda c: -c["score"])
    return {"cliente": cli.nombre, "candidatos": candidatos[:50], "total": len(candidatos)}


@router.post("/movimientos/{mov_id}/acreditar")
def acreditar_movimiento_a_cliente(
    mov_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Marca un movimiento como acreditado al cliente indicado, con la fecha indicada.
    Usado desde el flujo "Acreditar comprobante".

    Payload:
      - cliente_id: int (obligatorio)
      - fecha_acred: ISO date opcional (default = fecha del movimiento)
    """
    from app.models.cliente import Cliente
    from app.services.auditoria import registrar_log

    mov = db.query(MovimientoBanco).filter(MovimientoBanco.id == mov_id).first()
    if not mov:
        raise HTTPException(404, "Movimiento no encontrado")

    cliente_id = payload.get("cliente_id")
    q = db.query(Cliente).filter(Cliente.id == cliente_id)
    if not current_user.is_superadmin:
        q = q.filter(Cliente.organizacion_id == current_user.organizacion_id)
    cli = q.first()
    if not cli:
        raise HTTPException(404, "Cliente no encontrado")

    fecha_s = payload.get("fecha_acred")
    fecha_acred = None
    if fecha_s:
        try:
            fecha_acred = datetime.fromisoformat(fecha_s).date()
        except ValueError:
            pass
    if not fecha_acred:
        fecha_acred = mov.fecha or hoy_art()

    anterior = mov.cliente_acreditado
    mov.cliente_acreditado = cli.nombre
    mov.fecha_acred = fecha_acred
    db.flush()

    from app.models.planilla import Planilla, PlanillaRow
    from datetime import datetime as dt

    planilla_id_creada = None
    try:
        # 1. Buscar si ya existe una fila para este movimiento en cualquier planilla del cliente
        row_existente = (
            db.query(PlanillaRow)
              .join(Planilla, Planilla.id == PlanillaRow.planilla_id)
              .filter(Planilla.cliente_id == cli.id,
                      PlanillaRow.orden_movimiento_acreditado == mov.id)
              .first()
        )
        if row_existente:
            # Actualizar la fila existente en la planilla original
            row_existente.status = "ok"
            row_existente.monto = mov.monto
            row_existente.titular = row_existente.titular or mov.titular
            db.commit()
            planilla_id_creada = row_existente.planilla_id
        else:
            # 2. Buscar planilla original del cliente para este extracto (no manual)
            planilla = (
                db.query(Planilla)
                  .filter(Planilla.cliente_id == cli.id,
                          Planilla.extracto_id == mov.extracto_id,
                          ~Planilla.nombre_archivo.like("acreditacion manual%"))
                  .order_by(Planilla.id.desc())
                  .first()
            )
            # 3. Si no hay planilla original, buscar o crear la manual del dia
            if not planilla:
                inicio = dt.combine(fecha_acred, dt.min.time())
                fin    = dt.combine(fecha_acred, dt.max.time())
                planilla = (
                    db.query(Planilla)
                      .filter(Planilla.cliente_id == cli.id,
                              Planilla.fecha_carga >= inicio,
                              Planilla.fecha_carga <= fin,
                              Planilla.nombre_archivo.like("acreditacion manual%"))
                      .order_by(Planilla.id.desc())
                      .first()
                )
                if not planilla:
                    planilla = Planilla(
                        cliente_id=cli.id,
                        extracto_id=mov.extracto_id,
                        usuario_id=current_user.id,
                        organizacion_id=mov.organizacion_id or 1,
                        nombre_archivo=f"acreditacion manual {fecha_acred.day}.{fecha_acred.month}",
                        fecha_carga=dt.combine(fecha_acred, dt.min.time()),
                    )
                    db.add(planilla)
                    db.flush()

            db.add(PlanillaRow(
                planilla_id=planilla.id,
                organizacion_id=planilla.organizacion_id,
                monto=mov.monto,
                cuit=None,
                titular=mov.titular,
                status="ok",
                orden_movimiento_acreditado=mov.id,
            ))
            db.commit()
            planilla_id_creada = planilla.id
    except Exception as ex:
        db.rollback()
        mov = db.query(MovimientoBanco).filter(MovimientoBanco.id == mov_id).first()
        if mov:
            mov.cliente_acreditado = cli.nombre
            mov.fecha_acred = fecha_acred
            db.commit()
        logger.warning("Error acreditar: %s", ex)

    registrar_log(db, current_user.id, "movimientos_banco", mov.id, "ACREDITAR_MANUAL",
                  {"cliente": cli.nombre, "fecha_acred": str(fecha_acred),
                   "anterior": anterior, "planilla_id": planilla_id_creada})

    return {
        "ok": True,
        "mov_id": mov.id,
        "cliente": cli.nombre,
        "fecha_acred": fecha_acred.isoformat(),
        "planilla_id": planilla_id_creada,
    }


@router.delete("/{cliente_id}")
def borrar_cliente(cliente_id: int,
                   force: bool = False,
                   db: Session = Depends(get_db),
                   current_user: User = Depends(require_permission("delete_records"))):
    """
    Borra un cliente. Si tiene planillas asociadas y no se manda ?force=true,
    devuelve 409 con la cantidad de archivos para que el frontend pida
    confirmacion al usuario. Con force=true, borra cliente + planillas + filas
    y NULL al cliente_acreditado de los movimientos.
    """
    from app.models.cliente import Cliente
    from app.models.planilla import Planilla
    from app.services.auditoria import registrar_log

    q = db.query(Cliente).filter(Cliente.id == cliente_id)
    if not current_user.is_superadmin:
        q = q.filter(Cliente.organizacion_id == current_user.organizacion_id)
    cli = q.first()
    if not cli:
        raise HTTPException(404, "Cliente no encontrado")

    # Scope: usuarios no superadmin solo pueden borrar de su org
    if not current_user.is_superadmin and cli.organizacion_id != (current_user.organizacion_id or 1):
        raise HTTPException(403, "No podes borrar clientes de otra organizacion")

    planillas = db.query(Planilla).filter(Planilla.cliente_id == cliente_id).all()
    n_planillas = len(planillas)

    if n_planillas > 0 and not force:
        raise HTTPException(409, {
            "message": f"El cliente '{cli.nombre}' tiene {n_planillas} planilla(s) guardada(s). "
                       f"Mandá force=true para borrar TODO (cliente + planillas + acreditaciones).",
            "planillas": n_planillas,
            "nombre": cli.nombre,
        })

    nombre = cli.nombre
    try:
        # 1. Limpiar cliente_acreditado en movimientos que tenian este cliente
        # Filtramos por org para no afectar movs de otras orgs con mismo nombre
        movs_acreditados = db.query(MovimientoBanco).filter(
            MovimientoBanco.cliente_acreditado.ilike(nombre),
            MovimientoBanco.organizacion_id == cli.organizacion_id,
        ).all()
        for m in movs_acreditados:
            m.cliente_acreditado = None
            m.fecha_acred = None
        db.flush()

        # 2. Borrar planillas (cascade borra los rows)
        for p in planillas:
            db.delete(p)
        db.flush()

        # 3. Borrar cliente
        db.delete(cli)
        db.commit()

        registrar_log(db, current_user.id, "clientes", cliente_id, "DELETE",
                      {"nombre": nombre, "planillas_borradas": n_planillas,
                       "movimientos_liberados": len(movs_acreditados)})
        return {
            "ok": True,
            "mensaje": f"Cliente '{nombre}' borrado",
            "planillas_borradas": n_planillas,
            "movimientos_liberados": len(movs_acreditados),
        }
    except Exception as e:
        db.rollback()
        logger.error("Error borrar cliente: %s", e)
        raise HTTPException(500, "Error al borrar el cliente. Intentá de nuevo.")


@router.post("/{cliente_id}/share-link")
def generar_share_link(
    cliente_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Genera un link público de solo lectura para el estado de cuenta del cliente (expira en 7 días)."""
    from datetime import timedelta
    from jose import jwt as jose_jwt
    from app.config import get_settings
    from app.models.cliente import Cliente

    settings = get_settings()
    org_id = current_user.organizacion_id or 1
    cliente = db.query(Cliente).filter(Cliente.id == cliente_id, Cliente.organizacion_id == org_id).first()
    if not cliente:
        raise HTTPException(404, "Cliente no encontrado")

    exp = datetime.utcnow() + timedelta(days=7)
    payload = {
        "type": "share_cliente",
        "client_id": cliente_id,
        "org_id": org_id,
        "exp": exp,
    }
    token = jose_jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
    url = f"{settings.frontend_url}/p/{token}"
    return {
        "token": token,
        "url": url,
        "expires_at": exp.isoformat(),
        "cliente_nombre": cliente.nombre,
    }


@router.post("")
def crear_cliente(payload: dict,
                  db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user)):
    """Crea un nuevo cliente (carpeta) en la organizacion del usuario."""
    from app.models.cliente import Cliente
    from app.services.auditoria import registrar_log

    nombre = (payload.get("nombre") or "").strip()
    nombre = nombre[:1].upper() + nombre[1:] if nombre else nombre
    cuit_raw = (payload.get("cuit") or "").strip()
    cuit = cuit_raw or None
    org_id = payload.get("organizacion_id") or current_user.organizacion_id or 1

    if not nombre:
        raise HTTPException(400, "El nombre es obligatorio")

    if cuit:
        cuit_digits = cuit.replace("-", "").replace(" ", "")
        if not cuit_digits.isdigit() or len(cuit_digits) not in (10, 11):
            raise HTTPException(400, "CUIT inválido: debe tener 10 u 11 dígitos numéricos")
        cuit = cuit_digits

    # Scope: usuarios no superadmin solo pueden crear en su org
    if not can_switch_org(current_user, org_id) and org_id != (current_user.organizacion_id or 1):
        raise HTTPException(403, "Solo podes crear clientes en tu organizacion")

    # No duplicar por (nombre, org)
    existente = db.query(Cliente).filter(
        Cliente.nombre.ilike(nombre),
        Cliente.organizacion_id == org_id
    ).first()
    if existente:
        raise HTTPException(409, f"Ya existe el cliente '{existente.nombre}' en esta organizacion")

    c = Cliente(nombre=nombre, cuit=cuit, organizacion_id=org_id)
    db.add(c)
    db.commit()
    db.refresh(c)
    registrar_log(db, current_user.id, "clientes", c.id, "INSERT",
                  {"nombre": nombre, "organizacion_id": org_id})
    return {"id": c.id, "nombre": c.nombre, "cuit": c.cuit, "organizacion_id": c.organizacion_id}


@router.put("/{cliente_id}/renombrar")
def renombrar_cliente(
    cliente_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cambia el nombre de un cliente y actualiza todos los movimientos que lo referencian."""
    from app.models.cliente import Cliente
    from app.services.auditoria import registrar_log

    nuevo_nombre = (payload.get("nombre") or "").strip()
    nuevo_nombre = nuevo_nombre[:1].upper() + nuevo_nombre[1:] if nuevo_nombre else nuevo_nombre
    if not nuevo_nombre:
        raise HTTPException(400, "El nombre es obligatorio")

    q = db.query(Cliente).filter(Cliente.id == cliente_id)
    if not current_user.is_superadmin:
        q = q.filter(Cliente.organizacion_id == current_user.organizacion_id)
    cli = q.first()
    if not cli:
        raise HTTPException(404, "Cliente no encontrado")

    # Verificar que no exista otro cliente con ese nombre (case-insensitive)
    existente = db.query(Cliente).filter(
        Cliente.nombre.ilike(nuevo_nombre),
        Cliente.organizacion_id == cli.organizacion_id,
        Cliente.id != cliente_id,
    ).first()
    if existente:
        raise HTTPException(409, f"Ya existe el cliente '{existente.nombre}'")

    nombre_anterior = cli.nombre
    cli.nombre = nuevo_nombre

    # Actualizar referencias en movimientos
    db.query(MovimientoBanco).filter(
        MovimientoBanco.cliente_acreditado.ilike(nombre_anterior),
        MovimientoBanco.organizacion_id == cli.organizacion_id,
    ).update({"cliente_acreditado": nuevo_nombre}, synchronize_session=False)

    db.commit()
    registrar_log(db, current_user.id, "clientes", cli.id, "UPDATE",
                  {"nombre_anterior": nombre_anterior, "nombre_nuevo": nuevo_nombre})
    return {"id": cli.id, "nombre": cli.nombre}


@router.post("/{cliente_id}/fusionar")
def fusionar_clientes(
    cliente_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Fusiona cliente_id (source) dentro de target_id.
    Reasigna todas las planillas y movimientos del source al target, luego borra el source.
    """
    from app.models.cliente import Cliente
    from app.services.auditoria import registrar_log

    target_id = payload.get("target_id")
    if not target_id:
        raise HTTPException(400, "target_id es obligatorio")

    if cliente_id == target_id:
        raise HTTPException(400, "El cliente origen y destino deben ser distintos")


    source = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    target = db.query(Cliente).filter(Cliente.id == target_id).first()
    if not source or not target:
        raise HTTPException(404, "Cliente no encontrado")
    if source.organizacion_id != target.organizacion_id:
        raise HTTPException(400, "Los clientes deben pertenecer a la misma organización")
    if not current_user.is_superadmin and source.organizacion_id != (current_user.organizacion_id or 1):
        raise HTTPException(403, "Sin permiso para fusionar clientes de otra organización")

    # Reasignar planillas
    planillas_reasignadas = db.query(Planilla).filter(Planilla.cliente_id == cliente_id).count()
    db.query(Planilla).filter(Planilla.cliente_id == cliente_id).update(
        {"cliente_id": target_id}, synchronize_session=False
    )

    # Actualizar cliente_acreditado en movimientos
    movs_actualizados = db.query(MovimientoBanco).filter(
        MovimientoBanco.cliente_acreditado.ilike(source.nombre),
        MovimientoBanco.organizacion_id == source.organizacion_id,
    ).count()
    db.query(MovimientoBanco).filter(
        MovimientoBanco.cliente_acreditado.ilike(source.nombre),
        MovimientoBanco.organizacion_id == source.organizacion_id,
    ).update({"cliente_acreditado": target.nombre}, synchronize_session=False)

    nombre_source = source.nombre
    db.delete(source)
    db.commit()

    registrar_log(db, current_user.id, "clientes", target_id, "FUSIONAR",
                  {"source": nombre_source, "target": target.nombre,
                   "planillas_reasignadas": planillas_reasignadas,
                   "movimientos_actualizados": movs_actualizados})

    return {
        "ok": True,
        "mensaje": f"'{nombre_source}' fusionado en '{target.nombre}'",
        "planillas_reasignadas": planillas_reasignadas,
        "movimientos_actualizados": movs_actualizados,
    }


@router.put("/{cliente_id}/comision")
def actualizar_comision_cliente(
    cliente_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Setea o borra los % de comision del cliente. NULL = usa default de la org.
    Acepta: porcentaje_comision (general/TT), porcentaje_comision_local y
    porcentaje_comision_interior (cheques según CP). Solo actualiza los campos
    presentes en el payload."""
    from app.models.cliente import Cliente as Cli
    from app.services.auditoria import registrar_log
    from decimal import Decimal

    org_id = current_user.organizacion_id or 1
    q = db.query(Cli).filter(Cli.id == cliente_id)
    if not current_user.is_superadmin:
        q = q.filter(Cli.organizacion_id == org_id)
    cliente = q.first()
    if not cliente:
        raise HTTPException(404, "Cliente no encontrado")

    def _parse(raw):
        if raw is None or raw == "":
            return None
        try:
            pct = Decimal(str(raw))
        except Exception:
            raise HTTPException(400, "Porcentaje inválido")
        if pct < 0 or pct > 100:
            raise HTTPException(400, "El porcentaje debe estar entre 0 y 100")
        return pct

    # Solo tocar los campos que vengan en el payload (update parcial)
    for campo in ("porcentaje_comision", "porcentaje_comision_local", "porcentaje_comision_interior"):
        if campo in payload:
            setattr(cliente, campo, _parse(payload.get(campo)))

    db.commit()
    registrar_log(db, current_user.id, "clientes", cliente.id, "UPDATE", {
        "porcentaje_comision": str(cliente.porcentaje_comision),
        "porcentaje_comision_local": str(cliente.porcentaje_comision_local),
        "porcentaje_comision_interior": str(cliente.porcentaje_comision_interior),
    })
    return {
        "id": cliente.id,
        "nombre": cliente.nombre,
        "porcentaje_comision": float(cliente.porcentaje_comision) if cliente.porcentaje_comision is not None else None,
        "porcentaje_comision_local": float(cliente.porcentaje_comision_local) if cliente.porcentaje_comision_local is not None else None,
        "porcentaje_comision_interior": float(cliente.porcentaje_comision_interior) if cliente.porcentaje_comision_interior is not None else None,
    }

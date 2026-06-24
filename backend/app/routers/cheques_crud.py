"""Router cheques — CRUD principal, carga masiva OCR, portadores, foto e importación.

Rutas expuestas (bajo el prefix /cheques del router padre):
  POST   /bulk-ocr
  POST   /bulk-crear
  GET    /portadores
  POST   /portadores
  GET    /{cheque_id}
  PATCH  /{cheque_id}
  DELETE /{cheque_id}
  POST   /{cheque_id}/foto
  GET    /{cheque_id}/foto
  DELETE /{cheque_id}/foto
  POST   /importar

Nota: GET "" y POST "" (listar/crear cheque) están declarados directamente
en cheques.py (el agregador), no en este módulo — ver comentario en la
sección "CRUD principal" más abajo.
"""
from datetime import date
from decimal import Decimal
from typing import Optional, List
import io

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address
import openpyxl

from app.database import get_db
from app.middleware.auth import get_current_user, require_permission
from app.models.user import User
from app.models.cheque import Cheque
from app.models.portador import Portador
from app.models.cliente import Cliente
from app.services.motor_contable import registrar_cheque
from app.services.auditoria import registrar_log
from app.services.storage import upload_comprobante
from app.services.tz import hoy_art

from .cheques_common import (
    ChequeIn, PortadorIn, BulkCrearIn, FotoIn,
    _org_id, _local_interior, _cheque_dict, _parse_date,
)

router = APIRouter(tags=["cheques"])
limiter = Limiter(key_func=get_remote_address)


# ── Carga masiva OCR ──────────────────────────────────────────────

@router.post("/bulk-ocr")
async def bulk_ocr(
    fotos: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
):
    """Recibe hasta 30 fotos, aplica OCR a cada una en paralelo y devuelve los datos extraídos."""
    import asyncio
    import os
    import json

    MAX_FOTOS = 30
    if len(fotos) > MAX_FOTOS:
        raise HTTPException(400, f"Máximo {MAX_FOTOS} fotos por lote")
    if len(fotos) == 0:
        raise HTTPException(400, "Se requiere al menos una foto")

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(503, "OCR no configurado (falta GEMINI_API_KEY)")

    from routers.agente import _GEMINI_MODEL, _classify_gemini_error

    OCR_PROMPT = (
        "Extraé los datos de este cheque bancario argentino. "
        "Respondé SOLO con un JSON válido (sin texto extra, sin markdown), con estos campos "
        "(usá null si no está visible o no podés leerlo): "
        '{"numero": "string o null", "banco_origen": "string o null", "librador": "string o null", '
        '"monto": número_sin_formato_o_null, "fecha_emision": "YYYY-MM-DD o null", '
        '"fecha_deposito": "YYYY-MM-DD o null", "codigo_postal": "string o null"}'
    )

    async def _ocr_single(index: int, foto: UploadFile) -> dict:
        filename = foto.filename or f"foto_{index}"
        base_result = {
            "index": index,
            "filename": filename,
            "numero": None,
            "banco_origen": None,
            "librador": None,
            "monto": None,
            "fecha_emision": None,
            "fecha_deposito": None,
            "codigo_postal": None,
            "local_interior": None,
        }
        try:
            raw = await foto.read()
            mime_type = foto.content_type or "image/jpeg"
            # Llamada a Gemini en thread pool para no bloquear el event loop
            loop = asyncio.get_event_loop()

            def _call():
                import google.generativeai as genai
                import time as _time
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel(_GEMINI_MODEL)
                image_part = genai.protos.Part(
                    inline_data=genai.protos.Blob(mime_type=mime_type, data=raw)
                )
                for attempt in range(2):
                    try:
                        resp = model.generate_content([image_part, OCR_PROMPT])
                        try:
                            texto = resp.text.strip()
                        except Exception:
                            return {}
                        if not texto:
                            return {}
                        if texto.startswith("```"):
                            lines = [l for l in texto.split("\n") if not l.startswith("```")]
                            texto = "\n".join(lines).strip()
                        return json.loads(texto)
                    except Exception as ex:
                        msg = str(ex).upper()
                        is_transient = "RESOURCE_EXHAUSTED" in msg or "429" in str(ex)
                        if is_transient and attempt == 0:
                            _time.sleep(5)
                            continue
                        raise

            datos = await loop.run_in_executor(None, _call)
            cp = str(datos.get("codigo_postal") or "").strip() or None
            li = _local_interior(cp)
            return {
                **base_result,
                "numero":         str(datos["numero"]).strip()        if datos.get("numero")         else None,
                "banco_origen":   str(datos["banco_origen"]).strip()  if datos.get("banco_origen")   else None,
                "librador":       str(datos["librador"]).strip()      if datos.get("librador")        else None,
                "monto":          float(datos["monto"])               if datos.get("monto") is not None else None,
                "fecha_emision":  str(datos["fecha_emision"])         if datos.get("fecha_emision")   else None,
                "fecha_deposito": str(datos["fecha_deposito"])        if datos.get("fecha_deposito")  else None,
                "codigo_postal":  cp,
                "local_interior": li,
                "error":          False,
            }
        except json.JSONDecodeError:
            return {**base_result, "error": True, "error_msg": "Respuesta OCR inválida"}
        except Exception as ex:
            _, msg = _classify_gemini_error(ex)
            return {**base_result, "error": True, "error_msg": msg}

    tasks = [_ocr_single(i, foto) for i, foto in enumerate(fotos)]
    results = await asyncio.gather(*tasks)
    return {"items": list(results)}


@router.post("/bulk-crear")
def bulk_crear(
    body: BulkCrearIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Crea múltiples cheques en un solo request. Valida cliente por item; no aborta ante error parcial."""
    oid = _org_id(current_user, body.org_id)

    creados_cheques = []
    errores = []

    for idx, item in enumerate(body.items):
        try:
            cli = None
            if item.cliente_id:
                cli = db.query(Cliente).filter(
                    Cliente.id == item.cliente_id, Cliente.organizacion_id == oid
                ).first()
                if not cli:
                    errores.append({"index": idx, "msg": f"Cliente {item.cliente_id} no encontrado"})
                    continue
                if not cli.cuenta_contable_id:
                    errores.append({"index": idx, "msg": f"'{cli.nombre}' no tiene cuenta contable. Creala en Contabilidad → Clientes."})
                    continue

            if item.portador_id:
                if not db.query(Portador).filter(Portador.id == item.portador_id, Portador.organizacion_id == oid).first():
                    errores.append({"index": idx, "msg": f"Portador {item.portador_id} no encontrado"})
                    continue

            li = item.local_interior or _local_interior(item.codigo_postal)

            if item.porcentaje_comision is not None:
                pct_comision = Decimal(str(item.porcentaje_comision))
            elif cli:
                if li == "local" and cli.porcentaje_comision_local is not None:
                    pct_comision = cli.porcentaje_comision_local
                elif li == "interior" and cli.porcentaje_comision_interior is not None:
                    pct_comision = cli.porcentaje_comision_interior
                else:
                    pct_comision = cli.porcentaje_comision
            else:
                pct_comision = None

            monto_dec = Decimal(str(item.monto))
            comision_dec = Decimal("0")
            if pct_comision is not None:
                comision_dec = (monto_dec * pct_comision / Decimal("100")).quantize(Decimal("0.01"))

            fecha_dep = None
            if item.fecha_deposito:
                try:
                    from datetime import date as _date
                    fecha_dep = _date.fromisoformat(item.fecha_deposito[:10])
                except Exception:
                    fecha_dep = None
            fecha_dep = fecha_dep or hoy_art()

            fecha_emi = None
            if item.fecha_emision:
                try:
                    from datetime import date as _date
                    fecha_emi = _date.fromisoformat(item.fecha_emision[:10])
                except Exception:
                    fecha_emi = None

            c = Cheque(
                organizacion_id=oid,
                cliente_id=item.cliente_id,
                portador_id=item.portador_id,
                numero=item.numero,
                banco_origen=item.banco_origen,
                librador=item.librador,
                monto=monto_dec,
                comision=comision_dec,
                porcentaje_comision=pct_comision,
                codigo_postal=item.codigo_postal,
                local_interior=li,
                fecha_emision=fecha_emi,
                fecha_deposito=fecha_dep,
                estado="registrado",
                notas=item.notas,
                usuario_id=current_user.id,
            )
            db.add(c)
            db.flush()

            registrar_cheque(
                db=db, cheque_id=c.id, org_id=oid, usuario_id=current_user.id,
                titular=c.librador or "", monto=c.monto, comision=c.comision,
                fecha=fecha_dep,
            )
            registrar_log(db, current_user.id, "cheques", c.id, "INSERT",
                          {"monto": float(c.monto), "librador": c.librador,
                           "cliente_id": c.cliente_id, "bulk": True,
                           "fecha_deposito": str(fecha_dep)})
            creados_cheques.append(c)

        except Exception as ex:
            db.rollback()
            errores.append({"index": idx, "msg": str(ex)})
            continue

    db.commit()
    for c in creados_cheques:
        try:
            db.refresh(c)
        except Exception:
            pass

    return {
        "creados":  len(creados_cheques),
        "errores":  errores,
        "cheques":  [_cheque_dict(c) for c in creados_cheques],
    }


# ── Portadores ────────────────────────────────────────────────────

@router.get("/portadores")
def list_portadores(
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    oid = _org_id(current_user, org_id)
    items = db.query(Portador).filter(Portador.organizacion_id == oid).order_by(Portador.nombre).all()
    return [{"id": p.id, "nombre": p.nombre} for p in items]


@router.post("/portadores")
def crear_portador(
    body: PortadorIn,
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    oid = _org_id(current_user, org_id)
    nombre = body.nombre.strip()
    if not nombre:
        raise HTTPException(400, "Nombre requerido")
    p = Portador(organizacion_id=oid, nombre=nombre)
    db.add(p)
    db.commit()
    db.refresh(p)
    return {"id": p.id, "nombre": p.nombre}


# ── CRUD principal ────────────────────────────────────────────────
#
# list_cheques (GET "") y crear_cheque (POST "") viven en cheques.py
# (el agregador), no aquí: ese router SÍ tiene el prefix "/cheques"
# propio, así que un path vacío ahí es válido para FastAPI. Si se
# declararan en este router (sin prefix propio) y luego se incluyeran
# vía `include_router()`, FastAPI lanza `FastAPIError: Prefix and path
# cannot be both empty` porque la combinación prefix-vacío + path-vacío
# en el punto de inclusión queda ambigua.

@router.get("/{cheque_id}")
def get_cheque(
    cheque_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    oid = current_user.organizacion_id or 1
    c = db.query(Cheque).filter(Cheque.id == cheque_id).first()
    if not c:
        raise HTTPException(404, "Cheque no encontrado")
    if not current_user.is_superadmin and c.organizacion_id != oid:
        raise HTTPException(403, "Sin acceso")
    return _cheque_dict(c)


@router.patch("/{cheque_id}")
def editar_cheque(
    cheque_id: int,
    body: ChequeIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    oid = current_user.organizacion_id or 1
    c = db.query(Cheque).filter(Cheque.id == cheque_id).first()
    if not c:
        raise HTTPException(404, "Cheque no encontrado")
    if not current_user.is_superadmin and c.organizacion_id != oid:
        raise HTTPException(403, "Sin acceso")
    if c.estado not in ("registrado", "pendiente"):
        raise HTTPException(400, "Solo se pueden editar cheques en estado registrado")

    cambios = {}
    for field in ("cliente_id", "portador_id", "numero", "banco_origen", "librador",
                  "monto", "comision", "codigo_postal", "fecha_emision", "fecha_deposito", "notas"):
        val = getattr(body, field, None)
        if val is not None:
            cambios[field] = {"de": str(getattr(c, field)), "a": str(val)}
            setattr(c, field, val)
    if body.codigo_postal:
        c.local_interior = body.local_interior or _local_interior(body.codigo_postal)
    if body.porcentaje_comision is not None:
        c.porcentaje_comision = Decimal(str(body.porcentaje_comision))
    if cambios:
        registrar_log(db, current_user.id, "cheques", c.id, "UPDATE", cambios)
    db.commit()
    db.refresh(c)
    return _cheque_dict(c)


@router.delete("/{cheque_id}")
@limiter.limit("30/minute")
def eliminar_cheque(
    request: Request,
    cheque_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("delete_records")),
):
    oid = current_user.organizacion_id or 1
    c = db.query(Cheque).filter(Cheque.id == cheque_id).first()
    if not c:
        raise HTTPException(404, "Cheque no encontrado")
    if not current_user.is_superadmin and c.organizacion_id != oid:
        raise HTTPException(403, "Sin acceso")
    if c.estado not in ("registrado", "pendiente"):
        raise HTTPException(400, "Solo se pueden eliminar cheques en estado registrado")

    from app.services.motor_contable import reversar_asientos
    motivo = f"Cheque #{cheque_id} eliminado por {current_user.email}"
    # Revertir asiento nuevo (cheque_registro) y también los legacy por si existieran
    for mod in ("cheque_registro", "cheque_carga", "cheque_comision"):
        reversar_asientos(db, modulo=mod, referencia_id=cheque_id,
                          org_id=c.organizacion_id, usuario_id=current_user.id, motivo=motivo)

    registrar_log(db, current_user.id, "cheques", cheque_id, "DELETE",
                  {"monto": c.monto, "librador": c.librador, "estado": c.estado})
    db.delete(c)
    db.commit()
    return {"ok": True}


# ── Foto comprobante ──────────────────────────────────────────────

@router.post("/{cheque_id}/foto")
def subir_foto(
    cheque_id: int,
    body: FotoIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    oid = current_user.organizacion_id or 1
    c = db.query(Cheque).filter(Cheque.id == cheque_id).first()
    if not c:
        raise HTTPException(404, "Cheque no encontrado")
    if not current_user.is_superadmin and c.organizacion_id != oid:
        raise HTTPException(403, "Sin acceso")
    c.foto_comprobante = upload_comprobante(body.foto_base64, prefix=f"cheque/{c.organizacion_id}")
    db.commit()
    return {"ok": True, "tiene_foto": True}


@router.get("/{cheque_id}/foto")
def ver_foto(
    cheque_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    oid = current_user.organizacion_id or 1
    c = db.query(Cheque).filter(Cheque.id == cheque_id).first()
    if not c:
        raise HTTPException(404, "Cheque no encontrado")
    if not current_user.is_superadmin and c.organizacion_id != oid:
        raise HTTPException(403, "Sin acceso")
    if not c.foto_comprobante:
        raise HTTPException(404, "Sin foto")
    return {"cheque_id": cheque_id, "foto_base64": c.foto_comprobante}


@router.delete("/{cheque_id}/foto")
def eliminar_foto(
    cheque_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("delete_records")),
):
    oid = current_user.organizacion_id or 1
    c = db.query(Cheque).filter(Cheque.id == cheque_id).first()
    if not c:
        raise HTTPException(404, "Cheque no encontrado")
    if not current_user.is_superadmin and c.organizacion_id != oid:
        raise HTTPException(403, "Sin acceso")
    c.foto_comprobante = None
    db.commit()
    return {"ok": True}


# ── Importación masiva por Excel ──────────────────────────────────

@router.post("/importar")
async def importar_excel(
    file: UploadFile = File(...),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    oid = _org_id(current_user, org_id)
    ext = (file.filename or '').lower().split('.')[-1]
    if ext not in ('xlsx', 'xls'):
        raise HTTPException(400, "Solo se aceptan archivos .xlsx o .xls")

    content = await file.read()
    try:
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
    except Exception as e:
        raise HTTPException(400, f"No se pudo leer el archivo: {e}")

    if not rows:
        raise HTTPException(400, "El archivo está vacío")

    headers = [str(h).strip().lower() if h is not None else '' for h in rows[0]]
    COL = {
        'librador':       next((i for i, h in enumerate(headers) if 'librador' in h or 'titular' in h), None),
        'banco_origen':   next((i for i, h in enumerate(headers) if 'banco' in h and 'nuestro' not in h), None),
        'numero':         next((i for i, h in enumerate(headers) if 'numer' in h or 'cheque' in h), None),
        'monto':          next((i for i, h in enumerate(headers) if 'monto' in h or 'importe' in h), None),
        'comision':       next((i for i, h in enumerate(headers) if 'comis' in h), None),
        'fecha_emision':  next((i for i, h in enumerate(headers) if 'emisi' in h), None),
        'fecha_deposito': next((i for i, h in enumerate(headers) if 'deposito' in h or 'depósito' in h), None),
        'cliente':        next((i for i, h in enumerate(headers) if 'cliente' in h), None),
        'codigo_postal':  next((i for i, h in enumerate(headers) if 'codigo' in h or 'postal' in h), None),
        'notas':          next((i for i, h in enumerate(headers) if 'nota' in h or 'observ' in h), None),
    }
    if COL['monto'] is None:
        raise HTTPException(400, "Columna 'monto' requerida no encontrada")

    clientes_cache: dict[str, int] = {
        c.nombre.lower(): c.id
        for c in db.query(Cliente).filter(Cliente.organizacion_id == oid).all()
    }

    importados, errores = 0, []
    for i, row in enumerate(rows[1:], start=2):
        try:
            monto_raw = row[COL['monto']] if COL['monto'] is not None else None
            if not monto_raw:
                continue
            monto = Decimal(str(monto_raw).replace(',', '.').replace('$', '').strip())
            if monto <= 0:
                continue

            cliente_id = None
            if COL['cliente'] is not None and row[COL['cliente']]:
                cv = str(row[COL['cliente']]).strip()
                cliente_id = int(cv) if cv.isdigit() else clientes_cache.get(cv.lower())

            comision = Decimal("0")
            if COL['comision'] is not None and row[COL['comision']]:
                try:
                    comision = Decimal(str(row[COL['comision']]).replace(',', '.').replace('$', '').strip())
                except Exception:
                    pass

            cp = str(row[COL['codigo_postal']]).strip() if COL['codigo_postal'] is not None and row[COL['codigo_postal']] else None
            c = Cheque(
                organizacion_id=oid,
                cliente_id=cliente_id,
                librador=str(row[COL['librador']]).strip() if COL['librador'] is not None and row[COL['librador']] else None,
                banco_origen=str(row[COL['banco_origen']]).strip() if COL['banco_origen'] is not None and row[COL['banco_origen']] else None,
                numero=str(row[COL['numero']]).strip() if COL['numero'] is not None and row[COL['numero']] else None,
                monto=monto, comision=comision,
                codigo_postal=cp, local_interior=_local_interior(cp),
                fecha_emision=_parse_date(row[COL['fecha_emision']]) if COL['fecha_emision'] is not None else None,
                fecha_deposito=_parse_date(row[COL['fecha_deposito']]) if COL['fecha_deposito'] is not None else hoy_art(),
                notas=str(row[COL['notas']]).strip() if COL['notas'] is not None and row[COL['notas']] else None,
                estado="registrado", usuario_id=current_user.id,
            )
            db.add(c)
            db.flush()
            registrar_cheque(
                db=db, cheque_id=c.id, org_id=oid, usuario_id=current_user.id,
                titular=c.librador or "", monto=c.monto, comision=c.comision,
                fecha=c.fecha_deposito or hoy_art(),
            )
            importados += 1
        except Exception as ex:
            errores.append(f"Fila {i}: {ex}")

    db.commit()
    return {"importados": importados, "errores": errores}

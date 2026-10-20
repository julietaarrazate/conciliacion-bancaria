"""Ficha de proveedores propios de la organización.

Proveedor = a quien la organización le compra: sale de sus facturas recibidas
(IVA "recibido", Comprobantes por revisar) o se carga a mano. Las OP por cuenta
de un cliente (`pago_cliente`) pagan a proveedores DEL CLIENTE y nunca entran
acá (ver `validar_para_egreso`).
"""
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.egreso import Egreso
from app.models.iva_liquidacion import ComprobanteIva
from app.models.proveedor import CONDICIONES_IVA, Proveedor
from app.services.comprobantes_compra_service import cuit_valido, normalizar_cuit
from app.services.iva_liquidacion_service import TIPOS_NOTA_CREDITO

_CAMPOS = ("cuit", "razon_social", "condicion_iva", "email", "cbu", "notas")


class ProveedorInvalido(ValueError):
    pass


def _limpiar(campo: str, valor: Any) -> Optional[str]:
    if valor is None:
        return None
    if campo == "cuit":
        cuit = normalizar_cuit(valor)
        if cuit is None:
            return None
        if len(cuit) != 11:
            raise ProveedorInvalido("El CUIT debe tener 11 dígitos.")
        if not cuit_valido(cuit):
            raise ProveedorInvalido("El CUIT no es válido (revisá los dígitos).")
        return cuit
    texto = str(valor).strip() or None
    if campo == "razon_social" and not texto:
        raise ProveedorInvalido("La razón social es obligatoria.")
    if campo == "condicion_iva" and texto and texto not in CONDICIONES_IVA:
        raise ProveedorInvalido("Condición frente al IVA inválida.")
    if campo == "cbu" and texto and not (texto.isdigit() and len(texto) == 22):
        raise ProveedorInvalido("El CBU/CVU debe tener 22 dígitos.")
    return texto


def _guardar(db: Session, prov: Proveedor) -> Proveedor:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ProveedorInvalido("Ya hay un proveedor con ese CUIT.")
    db.refresh(prov)
    return prov


def crear(db: Session, org_id: int, datos: Dict[str, Any], origen: str = "manual") -> Proveedor:
    if "razon_social" not in datos:
        raise ProveedorInvalido("La razón social es obligatoria.")
    valores = {c: _limpiar(c, datos.get(c)) for c in _CAMPOS}
    prov = Proveedor(organizacion_id=org_id, origen=origen, activo=True, **valores)
    db.add(prov)
    return _guardar(db, prov)


def actualizar(db: Session, prov: Proveedor, datos: Dict[str, Any]) -> Proveedor:
    for campo in _CAMPOS:
        if campo in datos:
            setattr(prov, campo, _limpiar(campo, datos[campo]))
    if "activo" in datos:
        prov.activo = bool(datos["activo"])
    return _guardar(db, prov)


def obtener_o_crear_por_cuit(db: Session, org_id: int, cuit: str, razon_social: Optional[str]) -> Proveedor:
    """Para facturas de compra de la org: el proveedor con ese CUIT, o uno nuevo.
    No pisa lo que ya esté cargado. No commitea."""
    prov = db.query(Proveedor).filter_by(organizacion_id=org_id, cuit=cuit).first()
    if prov is None:
        prov = Proveedor(organizacion_id=org_id, cuit=cuit, origen="comprobantes", activo=True,
                         razon_social=(razon_social or "").strip() or f"CUIT {cuit}")
        db.add(prov)
        db.flush()
    return prov


def sincronizar_desde_comprobantes(db: Session, org_id: int) -> int:
    """Da de alta los emisores de las facturas recibidas que todavía no están en
    la ficha. Idempotente. Devuelve cuántos creó."""
    existentes = {c for (c,) in db.query(Proveedor.cuit).filter(
        Proveedor.organizacion_id == org_id, Proveedor.cuit.isnot(None))}
    filas = (db.query(ComprobanteIva.cuit_contraparte, ComprobanteIva.denominacion)
             .filter(ComprobanteIva.organizacion_id == org_id,
                     ComprobanteIva.direccion == "recibido",
                     ComprobanteIva.cuit_contraparte.isnot(None))
             .order_by(ComprobanteIva.fecha.desc()).all())
    nuevos: Dict[str, str] = {}
    for cuit_raw, nombre in filas:
        cuit = normalizar_cuit(cuit_raw)
        if cuit and len(cuit) == 11 and cuit not in existentes and cuit not in nuevos:
            nuevos[cuit] = (nombre or "").strip() or f"CUIT {cuit}"
    for cuit, nombre in nuevos.items():
        db.add(Proveedor(organizacion_id=org_id, cuit=cuit, razon_social=nombre[:255],
                         origen="comprobantes", activo=True))
    db.commit()
    return len(nuevos)


def validar_para_egreso(db: Session, org_id: int, tipo: str, proveedor_id: Any) -> Optional[Proveedor]:
    """El proveedor de un pago: solo en pagos a proveedor y de la misma org."""
    if proveedor_id in (None, ""):
        return None
    if tipo != "proveedor":
        raise ProveedorInvalido(
            "Un proveedor de la ficha solo va en un pago a proveedor propio. Si es una OP por "
            "cuenta de un cliente, va a nombre del cliente con el proveedor en \"A favor de\".")
    try:
        pid = int(proveedor_id)
    except (TypeError, ValueError):
        raise ProveedorInvalido("proveedor_id inválido")
    prov = db.query(Proveedor).filter_by(id=pid, organizacion_id=org_id).first()
    if prov is None:
        raise ProveedorInvalido("Proveedor no encontrado en esta organización.")
    return prov


def listar(db: Session, org_id: int, q: Optional[str] = None,
           incluir_inactivos: bool = False) -> List[Dict[str, Any]]:
    """Proveedores con lo facturado (facturas recibidas, NC restan), lo pagado
    (pagos a proveedor vinculados) y el saldo."""
    query = db.query(Proveedor).filter(Proveedor.organizacion_id == org_id)
    if not incluir_inactivos:
        query = query.filter(Proveedor.activo.is_(True))
    if q and q.strip():
        patron = f"%{q.strip()}%"
        query = query.filter(Proveedor.razon_social.ilike(patron) | Proveedor.cuit.ilike(patron))
    provs = query.order_by(Proveedor.razon_social).all()

    pagado = dict(db.query(Egreso.proveedor_id, func.sum(Egreso.monto))
                  .filter(Egreso.organizacion_id == org_id, Egreso.proveedor_id.isnot(None),
                          Egreso.tipo == "proveedor")
                  .group_by(Egreso.proveedor_id).all())
    facturado: Dict[str, Decimal] = {}
    cuits = [p.cuit for p in provs if p.cuit]
    if cuits:
        for cuit, tipo, total in (db.query(ComprobanteIva.cuit_contraparte, ComprobanteIva.tipo_codigo,
                                           ComprobanteIva.imp_total)
                                  .filter(ComprobanteIva.organizacion_id == org_id,
                                          ComprobanteIva.direccion == "recibido",
                                          ComprobanteIva.incluido.isnot(False),
                                          ComprobanteIva.cuit_contraparte.in_(cuits))):
            signo = -1 if tipo in TIPOS_NOTA_CREDITO else 1
            facturado[cuit] = facturado.get(cuit, Decimal("0")) + signo * Decimal(str(total or 0))

    salida = []
    for p in provs:
        fact = facturado.get(p.cuit, Decimal("0")) if p.cuit else Decimal("0")
        pag = Decimal(str(pagado.get(p.id) or 0))
        salida.append({**proveedor_dict(p), "total_facturado": fact, "total_pagado": pag,
                       "saldo": fact - pag})
    return salida


def proveedor_dict(p: Proveedor) -> Dict[str, Any]:
    return {"id": p.id, "organizacion_id": p.organizacion_id, "cuit": p.cuit,
            "razon_social": p.razon_social, "condicion_iva": p.condicion_iva, "email": p.email,
            "cbu": p.cbu, "notas": p.notas, "origen": p.origen, "activo": p.activo}

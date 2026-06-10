"""Sembrado del plan de cuentas + reglas contables, por organización.

Idempotente: se puede correr en cada arranque y al crear una org sin duplicar.
Extraído de main.py (v3.13) para poder sembrar CUALQUIER organización, no solo
la Organización A (id=1). Así las orgs de prueba también llevan contabilidad.
"""

from __future__ import annotations

import logging
from sqlalchemy.orm import Session

from app.models.contabilidad import PlanCuenta, ReglaContable

logger = logging.getLogger(__name__)

# (codigo, nombre, tipo, parent_codigo, nivel)
PLAN = [
    ("1-0-0-0", "Activo",               "activo",    None,      1),
    ("2-0-0-0", "Pasivo",               "pasivo",    None,      1),
    ("3-0-0-0", "Resultado",            "resultado", None,      1),
    ("1-1-0-0", "Activo Corriente",     "activo",   "1-0-0-0",  2),
    ("1-2-0-0", "Activo no corriente",  "activo",   "1-0-0-0",  2),
    ("2-1-0-0", "Pasivo Corriente",     "pasivo",   "2-0-0-0",  2),
    ("3-1-0-0", "Ingresos",             "resultado","3-0-0-0",  2),
    ("3-2-0-0", "Gastos",               "resultado","3-0-0-0",  2),
    ("1-1-1-0", "Disponibilidades",     "activo",   "1-1-0-0",  3),
    ("1-1-2-0", "Créditos",             "activo",   "1-1-0-0",  3),
    ("1-2-1-0", "Bienes de Uso",        "activo",   "1-2-0-0",  3),
    ("2-1-1-0", "Pasivo a Confirmar",   "pasivo",   "2-1-0-0",  3),
    ("2-1-2-0", "Cliente",              "pasivo",   "2-1-0-0",  3),
    ("3-1-1-0", "Comisiones",           "resultado","3-1-0-0",  3),
    ("3-1-2-0", "Operaciones de cambio","resultado","3-1-0-0",  3),
    ("3-2-1-0", "Impuesto déb y créd",  "resultado","3-2-0-0",  3),
    ("3-2-2-0", "Gastos bancarios",     "resultado","3-2-0-0",  3),
    ("1-1-1-1", "Caja chica",           "activo",   "1-1-1-0",  4),
    ("1-1-1-2", "Efectivo",             "activo",   "1-1-1-0",  4),
    ("1-1-1-3", "Banco",                "activo",   "1-1-1-0",  4),
    ("1-1-1-3-1", "Banco Macro",        "activo",   "1-1-1-3",  5),
    ("2-1-1-1", "No identificado",      "pasivo",   "2-1-1-0",  4),
    ("2-1-2-1", "Green",                "pasivo",   "2-1-2-0",  4),
    ("2-1-2-2", "Tucu",                 "pasivo",   "2-1-2-0",  4),
    ("2-1-2-3", "Alojando",             "pasivo",   "2-1-2-0",  4),
]

# Cuentas adicionales — se agregan en cada boot a planes ya existentes (idempotente)
PLAN_PATCH = [
    ("1-1-1-3-1", "Banco Macro",          "activo",    "1-1-1-3",  5),
    # Cuentas cheques (pedido contador junio 2026)
    ("1-1-1-4",   "Banco 2",              "activo",    "1-1-1-0",  4),
    ("1-1-2-1",   "Cheques en cartera",   "activo",    "1-1-2-0",  4),
    ("1-1-2-2-0", "Créditos socio",       "activo",    "1-1-2-0",  4),
    ("1-1-2-2-1", "Socio 1",              "activo",    "1-1-2-2-0",5),
    ("2-1-3-0",   "Cheques",              "pasivo",    "2-1-0-0",  3),
    ("2-1-3-1",   "Cheques depositados",  "pasivo",    "2-1-3-0",  4),
    ("2-1-3-2",   "Cheques a depositar",  "pasivo",    "2-1-3-0",  4),
    ("3-1-3-0",   "Comisiones cheques",   "resultado", "3-1-0-0",  3),
    ("3-2-2-1",   "Gastos de rechazos",   "resultado", "3-2-2-0",  4),
]

# (evento, descripcion, debe_codigo, haber_codigo)
REGLAS = [
    ("carga_extracto",          "Carga extracto bancario",          "1-1-1-3", "2-1-0-0"),
    ("carga_planilla",          "Acreditación planilla cliente",    "2-1-0-0", "2-1-2-0"),
    ("carga_planilla_comision", "Comisión sobre planilla",          "2-1-2-0", "3-1-1-0"),
    ("carga_efectivo",          "Carga cobro en efectivo",          "1-1-1-2", "1-1-1-3"),
    ("carga_cheque",            "Carga cheque cliente",             "1-1-2-1", "2-1-2-0"),
    ("carga_cheque_comision",   "Comisión sobre cheque",            "1-1-2-1", "3-1-3-0"),
    ("acred_rechazo_banco",     "Acred/rechazo cheque — banco",     "1-1-1-3", "1-1-2-0"),
    ("acred_rechazo_pasivo",    "Acred/rechazo cheque — cliente",   "2-1-2-0", "1-1-2-0"),
    ("pago_cliente_banco",      "Pago cliente por banco",           "2-1-2-0", "1-1-1-3"),
    ("pago_cliente_efectivo",   "Pago cliente en efectivo",         "2-1-2-0", "1-1-1-2"),
    ("asig_gasto_banco",        "Gasto pagado por banco",           "3-2-0-0", "1-1-1-3"),
    ("asig_gasto_efectivo",     "Gasto pagado en efectivo",         "3-2-0-0", "1-1-1-2"),
]


def seed_contabilidad_org(db: Session, org_id: int) -> dict:
    """Siembra plan de cuentas + reglas para una organización. Idempotente.

    - Crea las cuentas base que falten (PLAN) respetando la jerarquía padre→hijo.
    - Agrega las cuentas del patch que falten (PLAN_PATCH).
    - Crea las reglas que falten (por evento).
    Devuelve un resumen {cuentas_creadas, reglas_creadas, total_cuentas, total_reglas}.
    """
    code_to_id = {
        c.codigo: c.id
        for c in db.query(PlanCuenta).filter(PlanCuenta.organizacion_id == org_id).all()
    }

    # ── Cuentas base + patch (PLAN primero por la jerarquía, luego PLAN_PATCH) ──
    cuentas_creadas = 0
    for codigo, nombre, tipo, parent_codigo, nivel in PLAN + PLAN_PATCH:
        if codigo in code_to_id:
            continue
        parent_id = code_to_id.get(parent_codigo) if parent_codigo else None
        c = PlanCuenta(
            codigo=codigo, nombre=nombre, tipo=tipo,
            parent_id=parent_id, nivel=nivel,
            activo=True, organizacion_id=org_id,
        )
        db.add(c)
        db.flush()
        code_to_id[codigo] = c.id
        cuentas_creadas += 1
    if cuentas_creadas:
        db.commit()

    # ── Reglas que falten (por evento) ──
    eventos_existentes = {
        r.evento
        for r in db.query(ReglaContable).filter(ReglaContable.organizacion_id == org_id).all()
    }
    reglas_creadas = 0
    for evento, descripcion, debe_codigo, haber_codigo in REGLAS:
        if evento in eventos_existentes:
            continue
        if debe_codigo not in code_to_id or haber_codigo not in code_to_id:
            logger.warning("org %s: cuenta %s o %s no encontrada para regla %s",
                           org_id, debe_codigo, haber_codigo, evento)
            continue
        db.add(ReglaContable(
            evento=evento, descripcion=descripcion,
            cuenta_debe_id=code_to_id[debe_codigo],
            cuenta_haber_id=code_to_id[haber_codigo],
            activo=True, organizacion_id=org_id,
        ))
        reglas_creadas += 1
    if reglas_creadas:
        db.commit()

    total_cuentas = db.query(PlanCuenta).filter(PlanCuenta.organizacion_id == org_id).count()
    total_reglas  = db.query(ReglaContable).filter(ReglaContable.organizacion_id == org_id).count()
    if cuentas_creadas or reglas_creadas:
        logger.info("Seed contable org %s: +%d cuentas, +%d reglas (total %d/%d)",
                    org_id, cuentas_creadas, reglas_creadas, total_cuentas, total_reglas)
    return {
        "cuentas_creadas": cuentas_creadas,
        "reglas_creadas": reglas_creadas,
        "total_cuentas": total_cuentas,
        "total_reglas": total_reglas,
    }


def seed_categorias_egreso_org(db: Session, org_id: int) -> int:
    """Siembra las categorías de egreso por defecto si la org no tiene ninguna."""
    from app.models.egreso import CategoriaEgreso
    if db.query(CategoriaEgreso).filter(CategoriaEgreso.organizacion_id == org_id).count() > 0:
        return 0
    nombres = ["Impuestos", "Bancarios", "Proveedores", "Alquiler", "Sueldos", "Otros"]
    for nombre in nombres:
        db.add(CategoriaEgreso(organizacion_id=org_id, nombre=nombre, activo=True))
    db.commit()
    logger.info("Categorías de egreso sembradas para org %s", org_id)
    return len(nombres)

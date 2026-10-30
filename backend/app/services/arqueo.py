"""Arqueo de caja del día: armado con el saldo arrastrado del día anterior.

Un solo lugar arma el arqueo nuevo (antes lo creaba `GET /caja/arqueo/hoy`, una escritura
dentro de un GET). Ahora:
- `GET /caja/arqueo/hoy` muestra el borrador sin guardarlo (`armar_arqueo_del_dia`).
- `PUT /caja/arqueo/hoy` y los pagos en efectivo lo crean al escribir (`obtener_o_crear_arqueo`).
Así el arqueo arranca con el saldo y los billetes del día anterior sin importar qué lo crea.
"""
from datetime import date

from sqlalchemy.orm import Session

from app.models.caja import ArqueoDiario, denominaciones_vacias


def armar_arqueo_del_dia(db: Session, org_id: int, fecha: date, usuario_id: int) -> ArqueoDiario:
    """Arqueo nuevo (sin agregarlo a la sesión) que arrastra el saldo del día anterior."""
    anterior = db.query(ArqueoDiario).filter(
        ArqueoDiario.organizacion_id == org_id,
        ArqueoDiario.fecha < fecha
    ).order_by(ArqueoDiario.fecha.desc()).first()

    saldo_inicial = anterior.caja_restante if anterior else 0
    dens_iniciales = anterior.denominaciones.copy() if anterior and anterior.denominaciones else denominaciones_vacias()

    # Descontar denominaciones usadas en los egresos en efectivo del día anterior
    if anterior:
        for eg in anterior.egresos:
            if eg.denominaciones_usadas:
                for den, cant in eg.denominaciones_usadas.items():
                    dens_iniciales[den] = max(0, int(dens_iniciales.get(den, 0)) - int(cant))

    return ArqueoDiario(
        organizacion_id=org_id,
        fecha=fecha,
        saldo_inicial=round(saldo_inicial, 2),
        pesos_agregados=0,
        ingresos=0,
        denominaciones=dens_iniciales,
        cerrado=False,
        creado_por=usuario_id,
    )


def buscar_arqueo(db: Session, org_id: int, fecha: date):
    return db.query(ArqueoDiario).filter(
        ArqueoDiario.organizacion_id == org_id,
        ArqueoDiario.fecha == fecha
    ).first()


def obtener_o_crear_arqueo(db: Session, org_id: int, fecha: date, usuario_id: int) -> ArqueoDiario:
    """El arqueo del día; si no existe lo crea (flush, sin commit) con el saldo arrastrado."""
    arqueo = buscar_arqueo(db, org_id, fecha)
    if not arqueo:
        arqueo = armar_arqueo_del_dia(db, org_id, fecha, usuario_id)
        db.add(arqueo)
        db.flush()
    return arqueo

"""
Servicio de aprendizaje supervisado para el motor de match.

Nivel 2: aprende de correcciones manuales.
Cuando el usuario cambia 'sin datos' → 'ok' en una fila,
extrae el patron que identifica a ese pagador y lo guarda.

En futuras conciliaciones, antes de declarar 'sin datos',
el motor consulta los patrones aprendidos para ese cliente/org.
"""

import re
from typing import Optional, List
from sqlalchemy.orm import Session
from app.models.patron_aprendido import PatronAprendido
from app.models.planilla import PlanillaRow
from app.models.extracto import MovimientoBanco


def _extraer_fragmento_titular(texto: Optional[str], max_palabras: int = 3) -> str:
    """Extrae palabras clave alfabeticas del titular (sin numeros, sin palabras cortas)."""
    if not texto:
        return ''
    palabras = [p for p in texto.lower().split() if len(p) > 3 and p.isalpha()]
    return ' '.join(palabras[:max_palabras])


def _extraer_numeros_clave(cuit: Optional[str], titular: Optional[str], referencia: Optional[str]) -> str:
    """Extrae todos los numeros significativos (6+ digitos) de los campos de planilla."""
    nums = set()
    for campo in [cuit, titular, referencia]:
        if campo:
            encontrados = re.findall(r'\b\d{6,22}\b', str(campo))
            nums.update(encontrados)
    return ','.join(sorted(nums))


def registrar_correccion(
    db: Session,
    row: PlanillaRow,
    cliente_nombre: str,
    org_id: int
) -> None:
    """
    Llamado cuando el usuario corrige manualmente una fila a 'ok'.
    Extrae el patron que identifica a este pagador y lo guarda/actualiza.
    """
    if not row.orden_movimiento_acreditado:
        return  # sin movimiento asociado no hay patron que aprender

    mov = db.query(MovimientoBanco).filter(
        MovimientoBanco.id == row.orden_movimiento_acreditado
    ).first()
    if not mov:
        return

    titular_extracto = _extraer_fragmento_titular(mov.titular)
    numeros = _extraer_numeros_clave(row.cuit, row.titular, getattr(row, 'referencia', None))
    titular_plan = _extraer_fragmento_titular(row.titular)

    # Si no hay nada que aprender, no guardar
    if not titular_extracto and not numeros:
        return

    # Buscar si ya existe un patron similar para este cliente
    patron_existente = db.query(PatronAprendido).filter(
        PatronAprendido.organizacion_id == org_id,
        PatronAprendido.cliente_nombre == cliente_nombre,
        PatronAprendido.titular_extracto_fragmento == titular_extracto
    ).first()

    if patron_existente:
        # Reforzar patron existente
        patron_existente.veces_visto += 1
        patron_existente.veces_correcto += 1
        if row.monto:
            patron_existente.monto_tipico = row.monto
    else:
        # Crear patron nuevo
        db.add(PatronAprendido(
            organizacion_id=org_id,
            cliente_nombre=cliente_nombre,
            titular_fragmento=titular_plan,
            numeros_clave=numeros,
            monto_tipico=row.monto,
            titular_extracto_fragmento=titular_extracto,
            veces_visto=1,
            veces_correcto=1,
            activo=True
        ))

    db.commit()


def buscar_por_patrones(
    db: Session,
    org_id: int,
    cliente_nombre: str,
    monto: float,
    cuit: Optional[str],
    titular: Optional[str],
    referencia: Optional[str],
    movimientos_libres: list,
    procesados: set
) -> Optional[MovimientoBanco]:
    """
    Busca un match usando patrones aprendidos de correcciones previas.
    Se llama ANTES de declarar 'sin datos', como ultima oportunidad.

    Logica:
    1. Carga los patrones activos de este cliente en esta org
    2. Para cada movimiento libre con el monto correcto,
       verifica si su titular matchea algun patron del cliente
    3. Si encuentra match con confianza suficiente (veces_correcto >= 2), retorna el mov
    """
    patrones = db.query(PatronAprendido).filter(
        PatronAprendido.organizacion_id == org_id,
        PatronAprendido.cliente_nombre == cliente_nombre,
        PatronAprendido.activo == True,
        PatronAprendido.veces_correcto >= 2  # solo patrones confirmados al menos 2 veces
    ).order_by(PatronAprendido.veces_correcto.desc()).all()

    if not patrones:
        return None

    numeros_plan = set()
    for campo in [cuit, titular, referencia]:
        if campo:
            numeros_plan.update(re.findall(r'\b\d{6,22}\b', str(campo)))

    for mov in movimientos_libres:
        if mov.id in procesados:
            continue
        titular_mov = (mov.titular or '').lower()
        nums_mov = set(re.findall(r'\b\d{6,22}\b', mov.titular or ''))

        for patron in patrones:
            # Match por fragmento de titular del extracto
            if patron.titular_extracto_fragmento and patron.titular_extracto_fragmento in titular_mov:
                return mov

            # Match por numeros en comun
            if patron.numeros_clave:
                nums_patron = set(patron.numeros_clave.split(','))
                if nums_patron & nums_mov:
                    return mov
                if numeros_plan & nums_mov:
                    return mov

    return None


def listar_patrones(db: Session, org_id: int, cliente_nombre: Optional[str] = None) -> list:
    """Lista los patrones aprendidos para una org, opcionalmente filtrados por cliente."""
    q = db.query(PatronAprendido).filter(
        PatronAprendido.organizacion_id == org_id,
        PatronAprendido.activo == True
    )
    if cliente_nombre:
        q = q.filter(PatronAprendido.cliente_nombre == cliente_nombre)
    return q.order_by(PatronAprendido.veces_correcto.desc()).all()

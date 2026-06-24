"""Export SICOSS (archivo de texto de ancho fijo para AFIP/ARCA "Mi Simplificación").

⚠️ IMPORTANTE — léase antes de usar en producción:

SICOSS es el formato de importación de novedades de Seguridad Social que usa
"Mi Simplificación" (ex-SICOSS) para generar la Declaración Jurada del F931.
La especificación oficial completa tiene ~80 columnas posicionales por
registro (datos del empleado, conceptos remunerativos/no remunerativos,
códigos de obra social, ART, situación de revista, actividad, zona, etc.)
y CAMBIA con el tiempo según resoluciones de AFIP/ARCA.

Cuadra NO tiene (todavía) los datos de origen para completar todas esas
columnas con certeza: no captura domicilio/CP del empleado, código de
actividad, código de zona, modalidad de contratación, obra social del
empleado, ni los conceptos no remunerativos por separado. Por eso este
exportador documenta explícitamente, columna por columna, cuáles valores
son CONFIABLES (vienen de datos reales que Cuadra ya tiene) y cuáles son
PLACEHOLDER (un valor por defecto fijo, documentado, que el usuario debe
revisar/completar antes de importar el archivo a Mi Simplificación).

Preferimos un archivo honestamente incompleto (con placeholders explícitos
y advertencias) a uno que aparente estar completo y tenga datos inventados
que AFIP rechace o, peor, que se acepten silenciosamente con valores
incorrectos.

Layout implementado (subconjunto de columnas, ancho fijo, sin separadores):
  Posición   Largo  Campo                          Confiabilidad
  --------   -----  ------------------------------ --------------------------
  1-11       11     CUIL del empleado               CONFIABLE (Empleado.cuil)
  12-41      30     Apellido y nombre                CONFIABLE (Empleado.nombre)
  42         1      Código de situación de revista   PLACEHOLDER fijo "1" (activo)
  43-44      2      Código de condición              PLACEHOLDER fijo "00"
  45-46      2      Código de actividad              PLACEHOLDER fijo "00"
  47-48      2      Código de zona                   PLACEHOLDER fijo "00"
  49-58      10     Remuneración total (bruto)       CONFIABLE (sueldo_bruto, en centavos)
  59-68      10     Remuneración imponible jubilatoria CONFIABLE (= bruto, mismo criterio
                                                       que el cálculo de aportes; no hay
                                                       topes/mínimos de SIPA aplicados)
  69-78      10     Aporte jubilatorio del empleado   CONFIABLE (total_aportes)
  79-88      10     Contribución patronal             CONFIABLE (total_contribuciones)
  89-98      10     Retención de Ganancias 4ta cat.   CONFIABLE si el módulo de Ganancias
                                                       está activo; 0 si no (no es un campo
                                                       estándar de SICOSS — se agrega al final
                                                       del registro como dato de gestión extra,
                                                       NO ocupa una columna oficial del layout)
  99-106      8     Fecha de ingreso (AAAAMMDD)       CONFIABLE si Empleado.fecha_ingreso está
                                                       cargada; placeholder "00000000" si no.

Los montos se exportan en CENTAVOS (sin separador decimal, como exige el
formato fixed-width real de SICOSS) rellenados con ceros a la izquierda.
Los textos se rellenan con espacios a la derecha (ljust) y se truncan si
exceden el ancho de columna.

ANTES DE IMPORTAR ESTE ARCHIVO A AFIP: verificar contra la última
especificación vigente de "Mi Simplificación" — puede requerir completar o
ajustar las columnas marcadas como PLACEHOLDER, agregar conceptos no
remunerativos, código de obra social, modalidad de contratación, etc.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.sueldos import LiquidacionSueldoPeriodo, DetalleLiquidacionEmpleado, Empleado


# Ancho total del registro (suma de los campos documentados arriba).
ANCHO_REGISTRO = 11 + 30 + 1 + 2 + 2 + 2 + 10 + 10 + 10 + 10 + 10 + 8

# Placeholders documentados (ver docstring del módulo).
_PLACEHOLDER_SITUACION_REVISTA = "1"
_PLACEHOLDER_CONDICION = "00"
_PLACEHOLDER_ACTIVIDAD = "00"
_PLACEHOLDER_ZONA = "00"
_PLACEHOLDER_FECHA = "00000000"


def _centavos(monto) -> str:
    """Convierte un Decimal/float de pesos a centavos, string de 10 dígitos
    rellenado con ceros a la izquierda (formato fixed-width SICOSS)."""
    if monto is None:
        monto = Decimal("0")
    if not isinstance(monto, Decimal):
        monto = Decimal(str(monto))
    centavos = int((monto * 100).to_integral_value())
    if centavos < 0:
        centavos = 0  # SICOSS no admite negativos en estos campos
    s = str(centavos)
    if len(s) > 10:
        s = s[-10:]  # truncado defensivo; no debería ocurrir con montos reales
    return s.zfill(10)


def _texto(valor: str, ancho: int) -> str:
    valor = (valor or "").strip()
    return valor[:ancho].ljust(ancho)


def _cuil(cuil: str | None) -> str:
    """CUIL sin guiones, 11 dígitos. Si falta o es inválido, se completa con
    ceros (PLACEHOLDER) — el archivo es importable pero ese registro deberá
    corregirse manualmente antes de presentar."""
    if not cuil:
        return "0" * 11
    digits = "".join(c for c in cuil if c.isdigit())
    return digits.zfill(11)[:11] if digits else "0" * 11


def generar_archivo_sicoss(db: Session, organizacion_id: int, periodo: str) -> bytes:
    """Genera el archivo SICOSS (texto, ancho fijo) de una liquidación ya
    calculada para el período dado.

    Un registro por cada DetalleLiquidacionEmpleado de la liquidación (un
    empleado activo al momento de calcularse la liquidación). El archivo NO
    se genera para liquidaciones en estado "borrador" — debe estar al menos
    aprobada (el caller/router valida esto y devuelve 400 si no).

    Devuelve bytes (codificación latin-1, estándar para archivos de SUSS/AFIP
    que no toleran UTF-8 con BOM ni caracteres multibyte).
    """
    liq = (
        db.query(LiquidacionSueldoPeriodo)
        .filter(
            LiquidacionSueldoPeriodo.organizacion_id == organizacion_id,
            LiquidacionSueldoPeriodo.periodo == periodo,
        )
        .first()
    )
    if liq is None:
        raise ValueError(f"No hay liquidación calculada para el período {periodo}")

    detalles = (
        db.query(DetalleLiquidacionEmpleado)
        .filter(DetalleLiquidacionEmpleado.liquidacion_periodo_id == liq.id)
        .order_by(DetalleLiquidacionEmpleado.id.asc())
        .all()
    )

    lineas = []
    for d in detalles:
        emp = db.query(Empleado).filter(Empleado.id == d.empleado_id).first()
        cuil = _cuil(emp.cuil if emp else None)
        nombre = _texto(emp.nombre if emp else "", 30)
        fecha_ingreso = (
            emp.fecha_ingreso.strftime("%Y%m%d")
            if emp and emp.fecha_ingreso
            else _PLACEHOLDER_FECHA
        )

        campos = [
            cuil,
            nombre,
            _PLACEHOLDER_SITUACION_REVISTA,
            _PLACEHOLDER_CONDICION,
            _PLACEHOLDER_ACTIVIDAD,
            _PLACEHOLDER_ZONA,
            _centavos(d.sueldo_bruto),
            _centavos(d.sueldo_bruto),  # imponible jubilatoria ≈ bruto (sin topes SIPA)
            _centavos(d.total_aportes),
            _centavos(d.total_contribuciones),
            _centavos(d.retencion_ganancias),
            fecha_ingreso,
        ]
        linea = "".join(campos)
        assert len(linea) == ANCHO_REGISTRO, (
            f"Registro SICOSS con ancho incorrecto: {len(linea)} != {ANCHO_REGISTRO}"
        )
        lineas.append(linea)

    contenido = "\r\n".join(lineas)
    if lineas:
        contenido += "\r\n"
    return contenido.encode("latin-1", errors="replace")

"""Lectura de extractos con IA (Gemini) — último recurso del embudo.

Se usa solo si el PDF está escaneado, si la lectura sin IA no encontró
movimientos o no cierra, o si la persona lo pidió. Nunca lanza: cualquier
problema vuelve como alerta.

- PDF con texto: se manda el TEXTO extraído (respetando columnas) en tandas de
  hasta 4 páginas: es más barato que mandar el PDF y evita que una respuesta
  larga se corte por el límite de salida del modelo.
- PDF escaneado: se manda el PDF (hasta 15 MB, límite de Gemini inline).

Costura para tests: `lector_ia(mime_type, contenido) -> dict crudo`. Los tests la
reemplazan con monkeypatch; el lector la busca como atributo del módulo.
"""

from __future__ import annotations

import logging
import os
from datetime import date
from decimal import Decimal
from typing import Callable, Optional

from app.services.decimal_utils import parse_importe_ar

from .fechas import ContextoFechas, parsear_fecha
from .texto import Documento, texto_con_columnas

logger = logging.getLogger(__name__)

PAGINAS_POR_TANDA = 4
MAX_BYTES_PDF_IA = 15 * 1024 * 1024
MAX_MOVIMIENTOS = 5000
_LIMITE_DIARIO = int(os.environ.get("EXTRACTOS_PDF_IA_DAILY_LIMIT", "100"))

PROMPT_EXTRACTO = (
    "Sos un lector de extractos bancarios argentinos (resúmenes de cuenta). Te paso el "
    "resumen (o una parte: el texto indica qué páginas son). Devolvé SOLO un JSON válido, "
    "sin texto extra ni markdown, con este formato exacto:\n"
    '{"banco": "nombre del banco" o null, "periodo_desde": "YYYY-MM-DD" o null, '
    '"periodo_hasta": "YYYY-MM-DD" o null, "saldo_inicial": "1234.56" o null, '
    '"saldo_final": "1234.56" o null, "movimientos": [{"fecha": "YYYY-MM-DD", '
    '"descripcion": "texto", "debito": "1234.56" o null, "credito": "1234.56" o null, '
    '"importe": "-1234.56" o null, "saldo": "1234.56" o null}]}\n'
    "Reglas:\n"
    "- Un elemento por cada movimiento, en el MISMO orden en que aparecen. No inventes, no "
    "resumas y no agrupes movimientos.\n"
    "- NO son movimientos: saldo anterior/inicial, saldo final/actual, transporte, "
    "subtotales ni totales. El saldo anterior va en saldo_inicial y el saldo final en "
    "saldo_final (null si no aparecen en esta parte).\n"
    "- Importes como texto con punto decimal y sin separador de miles: si ves "
    "'$ 1.234,56' devolvé \"1234.56\". Un importe con '-' adelante o atrás o entre "
    "paréntesis es negativo.\n"
    "- Si el importe está en una columna de débitos poné \"debito\"; si está en créditos, "
    "\"credito\" (ambos en positivo). Si hay una sola columna de importe, poné \"importe\" "
    "con signo: negativo para débitos/egresos, positivo para créditos/ingresos.\n"
    "- \"saldo\" es el saldo que muestra esa fila (null si no tiene).\n"
    "- Si la fecha no trae año, deducilo del período del resumen.\n"
    "- Si el resumen tiene más de una cuenta (por ejemplo cuenta corriente y caja de "
    "ahorro), devolvé SOLO los movimientos de la primera cuenta.\n"
    "- descripcion: el concepto completo, con sus renglones de continuación (nombres, "
    "CUIT, CBU, números de referencia).\n"
    "- Si un dato no está, usá null."
)


class IaNoDisponible(Exception):
    pass


class IaLimiteDiario(Exception):
    pass


_contador = None


def ia_disponible() -> bool:
    """True si hay GEMINI_API_KEY (la IA está configurada en el servidor)."""
    return bool(os.environ.get("GEMINI_API_KEY", "").strip())


def _lector_ia_default(mime_type: str, contenido: bytes) -> dict:
    """Llama a Gemini con el mismo helper que el OCR de cheques y facturas."""
    from app.routers.agente import _call_gemini_ocr, _check_limit, _make_counter

    global _contador
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise IaNoDisponible("La lectura con IA no está configurada (falta GEMINI_API_KEY).")
    if _contador is None:
        _contador = _make_counter()
    if not _check_limit(_contador, _LIMITE_DIARIO):
        raise IaLimiteDiario("Se alcanzó el límite diario de lecturas de extractos con IA. Probá mañana.")
    return _call_gemini_ocr(api_key, mime_type, contenido, PROMPT_EXTRACTO)


# Inyectable en tests: (mime_type, contenido) -> dict (o list) crudo de la IA.
lector_ia: Callable[[str, bytes], dict] = _lector_ia_default


def _alerta(nivel: str, codigo: str, mensaje: str) -> dict:
    return {"nivel": nivel, "codigo": codigo, "mensaje": mensaje}


def _fecha(raw, ctx: ContextoFechas) -> Optional[date]:
    if raw is None:
        return None
    s = str(raw).strip()[:10]
    try:
        return date.fromisoformat(s)
    except ValueError:
        pass
    return ctx.resolver(parsear_fecha(s))


def _texto(raw, largo: int = 500) -> str:
    if raw is None:
        return ""
    return " ".join(str(raw).split())[:largo]


def _partes(crudo) -> list[dict]:
    """La IA puede devolver un objeto, una lista de objetos o una lista de filas."""
    if isinstance(crudo, dict):
        return [crudo]
    if isinstance(crudo, list):
        if crudo and all(isinstance(x, dict) and "movimientos" in x for x in crudo):
            return list(crudo)
        filas = [x for x in crudo if isinstance(x, dict)]
        return [{"movimientos": filas}] if filas else []
    return []


def normalizar_respuesta(crudos: list, ctx: ContextoFechas) -> dict:
    """Une las respuestas de cada tanda y normaliza montos (Decimal) y fechas."""
    movimientos: list[dict] = []
    saldo_inicial = saldo_final = None
    desde = hasta = None
    banco = None
    for crudo in crudos:
        for parte in _partes(crudo):
            if saldo_inicial is None:
                saldo_inicial = parse_importe_ar(parte.get("saldo_inicial"))
            sf = parse_importe_ar(parte.get("saldo_final"))
            if sf is not None:
                saldo_final = sf
            d, h = _fecha(parte.get("periodo_desde"), ctx), _fecha(parte.get("periodo_hasta"), ctx)
            desde = min(filter(None, (desde, d)), default=None)
            hasta = max(filter(None, (hasta, h)), default=None)
            banco = banco or (_texto(parte.get("banco"), 80) or None)
            filas = parte.get("movimientos")
            if not isinstance(filas, list):
                continue
            for m in filas:
                if not isinstance(m, dict) or len(movimientos) >= MAX_MOVIMIENTOS:
                    continue
                deb = parse_importe_ar(m.get("debito"))
                cred = parse_importe_ar(m.get("credito"))
                if (deb or cred):
                    monto = abs(cred or Decimal("0")) - abs(deb or Decimal("0"))
                else:
                    monto = parse_importe_ar(m.get("importe"))
                if monto is None or monto == 0:
                    continue
                movimientos.append({
                    "fecha": _fecha(m.get("fecha"), ctx),
                    "descripcion": _texto(m.get("descripcion")),
                    "monto": monto,
                    "saldo": parse_importe_ar(m.get("saldo")),
                })
    return {
        "movimientos": movimientos,
        "saldo_inicial": saldo_inicial,
        "saldo_final": saldo_final,
        "periodo": (desde, hasta) if desde and hasta and desde <= hasta else None,
        "banco": banco,
    }


def _mensaje_error(ex: Exception) -> str:
    if isinstance(ex, ValueError):      # json.JSONDecodeError: respuesta cortada o con texto extra
        return "la respuesta no se pudo interpretar. Probá de nuevo."
    try:
        from app.routers.agente import _classify_gemini_error

        _, msg = _classify_gemini_error(ex)
        return msg
    except Exception:  # pragma: no cover - import roto
        return "La IA no está disponible en este momento."


def leer_con_ia(
    doc: Optional[Documento],
    contenido: bytes,
    ctx: ContextoFechas,
    *,
    escaneado: bool,
) -> tuple[Optional[dict], list[dict], bool]:
    """(resultado normalizado | None, alertas, ia_usada). Nunca lanza."""
    alertas: list[dict] = []
    tandas: list[tuple[str, bytes]] = []
    if escaneado or doc is None:
        if len(contenido) > MAX_BYTES_PDF_IA:
            alertas.append(_alerta(
                "aviso", "ia_archivo_grande",
                "El PDF escaneado pesa más de 15 MB y no se puede leer con IA. "
                "Probá escanearlo en menor resolución o cargá los movimientos a mano.",
            ))
            return None, alertas, False
        tandas.append(("application/pdf", contenido))
    else:
        total = doc.paginas
        for inicio in range(1, total + 1, PAGINAS_POR_TANDA):
            fin = min(total, inicio + PAGINAS_POR_TANDA - 1)
            cabecera = f"Extracto bancario: páginas {inicio} a {fin} de {total}."
            if ctx.periodo:
                d, h = ctx.periodo
                cabecera += f" Período del resumen: {d:%d/%m/%Y} al {h:%d/%m/%Y}."
            texto = texto_con_columnas(doc, set(range(inicio, fin + 1)))
            if texto.strip():
                tandas.append(("text/plain", (cabecera + "\n\n" + texto).encode("utf-8")))
    if not tandas:
        return None, alertas, False

    crudos = []
    usada = False
    for mime, datos in tandas:
        try:
            usada = True
            crudos.append(lector_ia(mime, datos))
        except IaNoDisponible:
            alertas.append(_alerta(
                "aviso", "ia_no_disponible",
                "La lectura con IA no está configurada en el servidor: revisá los movimientos a mano.",
            ))
            return None, alertas, usada
        except IaLimiteDiario as ex:
            alertas.append(_alerta("aviso", "ia_limite", str(ex)))
            return None, alertas, usada
        except Exception as ex:
            logger.warning("Lectura de extracto con IA falló: %s", ex)
            alertas.append(_alerta(
                "aviso", "ia_error",
                f"No se pudo leer el PDF con IA: {_mensaje_error(ex)}",
            ))
            return None, alertas, usada
    resultado = normalizar_respuesta(crudos, ctx)
    if not resultado["movimientos"]:
        alertas.append(_alerta("aviso", "ia_sin_movimientos", "La IA no encontró movimientos en el PDF."))
    return resultado, alertas, usada

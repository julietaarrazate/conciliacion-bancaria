"""
Servicio de importación de extractos bancarios.
Soporta: CSV (formato estándar argentino) y OFX/QFX básico.

Formato CSV esperado (separador ;):
  Fecha;Descripción;Débito;Crédito;Referencia
  15/01/2024;Transferencia entrante;;150000.00;TRF-001
  16/01/2024;Pago servicios;8500.00;;FAC-123
"""
import csv
import io
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation


@dataclass
class ParsedTransaction:
    transaction_date: date
    description: str
    amount: Decimal          # positivo = crédito, negativo = débito
    reference: str | None


class ImportError(Exception):
    pass


def parse_csv(content: bytes, encoding: str = "utf-8") -> list[ParsedTransaction]:
    """
    Parsea un extracto bancario en CSV.
    Intenta detectar el separador automáticamente (; o ,).
    """
    text = content.decode(encoding, errors="replace")
    # Detectar separador
    sep = ";" if text.count(";") > text.count(",") else ","

    reader = csv.DictReader(io.StringIO(text), delimiter=sep)
    transactions: list[ParsedTransaction] = []

    for i, row in enumerate(reader, start=2):
        try:
            # Normalizar nombres de columnas (case-insensitive, sin espacios)
            row = {k.strip().lower(): v.strip() for k, v in row.items() if k}

            fecha_raw = row.get("fecha") or row.get("date") or row.get("f.")
            if not fecha_raw:
                continue

            desc = row.get("descripción") or row.get("descripcion") or row.get("concepto") or row.get("description") or ""
            debito_raw = row.get("débito") or row.get("debito") or row.get("debit") or "0"
            credito_raw = row.get("crédito") or row.get("credito") or row.get("credit") or "0"
            referencia = row.get("referencia") or row.get("reference") or row.get("nro.") or None

            fecha = _parse_date(fecha_raw)
            debito = _parse_amount(debito_raw)
            credito = _parse_amount(credito_raw)

            # crédito es positivo, débito es negativo
            amount = credito - debito
            if amount == Decimal("0"):
                continue

            transactions.append(ParsedTransaction(
                transaction_date=fecha,
                description=desc,
                amount=amount,
                reference=referencia if referencia else None,
            ))
        except (ValueError, InvalidOperation) as e:
            raise ImportError(f"Error en fila {i}: {e}") from e

    if not transactions:
        raise ImportError("No se encontraron transacciones válidas en el archivo")

    return transactions


def parse_ofx(content: bytes) -> list[ParsedTransaction]:
    """
    Parser básico de OFX/QFX (formato SGML, sin XML completo).
    Extrae los bloques <STMTTRN>.
    """
    text = content.decode("latin-1", errors="replace")
    transactions: list[ParsedTransaction] = []

    blocks = text.split("<STMTTRN>")
    for block in blocks[1:]:  # primer elemento es el header
        end = block.find("</STMTTRN>")
        if end != -1:
            block = block[:end]

        amount_raw = _ofx_tag(block, "TRNAMT")
        date_raw = _ofx_tag(block, "DTPOSTED")
        memo = _ofx_tag(block, "MEMO") or _ofx_tag(block, "NAME") or "Sin descripción"
        fitid = _ofx_tag(block, "FITID")

        if not amount_raw or not date_raw:
            continue

        try:
            amount = Decimal(amount_raw.replace(",", "."))
            fecha = _parse_ofx_date(date_raw)
            transactions.append(ParsedTransaction(
                transaction_date=fecha,
                description=memo,
                amount=amount,
                reference=fitid,
            ))
        except (ValueError, InvalidOperation):
            continue

    return transactions


def detect_and_parse(filename: str, content: bytes) -> list[ParsedTransaction]:
    """Detecta el formato por extensión y parsea."""
    ext = filename.lower().split(".")[-1]
    if ext in ("ofx", "qfx"):
        return parse_ofx(content)
    elif ext == "csv":
        return parse_csv(content)
    else:
        # Intentar CSV como fallback
        try:
            return parse_csv(content)
        except ImportError:
            raise ImportError(f"Formato no soportado: {ext}. Usar CSV u OFX.")


# ── helpers ────────────────────────────────────────────────────────────────

def _parse_date(raw: str) -> date:
    """Soporta DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD."""
    raw = raw.strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            from datetime import datetime
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Fecha no reconocida: '{raw}'")


def _parse_amount(raw: str) -> Decimal:
    """Limpia separadores de miles y convierte a Decimal."""
    clean = raw.strip().replace("$", "").replace(" ", "")
    # Detectar si usa . como separador de miles y , como decimal (formato argentino)
    if "," in clean and "." in clean:
        # 1.500,75 → 1500.75
        clean = clean.replace(".", "").replace(",", ".")
    elif "," in clean:
        clean = clean.replace(",", ".")
    return Decimal(clean) if clean else Decimal("0")


def _ofx_tag(text: str, tag: str) -> str | None:
    start = text.find(f"<{tag}>")
    if start == -1:
        return None
    start += len(tag) + 2
    end = text.find("\n", start)
    value = text[start:end if end != -1 else len(text)].strip()
    # Remover closing tag si existe
    if f"</{tag}>" in value:
        value = value.split(f"</{tag}>")[0]
    return value or None


def _parse_ofx_date(raw: str) -> date:
    """OFX usa YYYYMMDD o YYYYMMDDHHMMSS."""
    raw = raw.strip()[:8]
    from datetime import datetime
    return datetime.strptime(raw, "%Y%m%d").date()

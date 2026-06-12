"""
Export de asientos contables a formatos importables por software argentino.

Formatos soportados:
  csv       — CSV genérico configurable (separador, encoding, formato fecha, columnas)
  tango     — TXT tab-separated, fecha DD/MM/YYYY, montos con coma decimal
  holistor  — TXT fecha;cuenta;debe;haber;leyenda
  regisoft  — CSV con headers Fecha,Cuenta,Detalle,Debe,Haber

Mapeo de cuentas:
  El código exportado es PlanCuenta.codigo, SALVO que en Organizacion.configuracion
  exista la clave "mapeo_cuentas_export": {"1-1-1-3-1": "11030001", ...}.
  Si una cuenta no tiene mapeo y el formato NO es "csv", se incluye en la lista
  de advertencias devuelta como cuentas_sin_mapeo.

Retorna: (bytes, filename, content_type, cuentas_sin_mapeo: list[str])
"""

import io
import csv
from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session


def _fmt_fecha(d, formato: str) -> str:
    if d is None:
        return ""
    if isinstance(d, str):
        try:
            d = date.fromisoformat(d[:10])
        except ValueError:
            return str(d)
    if formato == "DD/MM/YYYY":
        return d.strftime("%d/%m/%Y")
    elif formato == "YYYY-MM-DD":
        return d.strftime("%Y-%m-%d")
    else:
        return d.strftime("%d/%m/%Y")


def _fmt_monto(v, coma_decimal: bool = False) -> str:
    """Formatea un monto Decimal/float como string sin separador de miles."""
    if v is None:
        return "0.00" if not coma_decimal else "0,00"
    d = Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    s = f"{d:.2f}"
    if coma_decimal:
        s = s.replace(".", ",")
    return s


def exportar_asientos(
    db: Session,
    org_id: int,
    desde: Optional[str],
    hasta: Optional[str],
    formato: str,
    config: Optional[dict] = None,
):
    """
    Exporta asientos del rango [desde, hasta] (ambos inclusive) en el formato pedido.

    Retorna: (bytes_content, filename, content_type, cuentas_sin_mapeo)
    """
    from app.models.contabilidad import Asiento, AsientoDetalle, PlanCuenta
    from app.models.organizacion import Organizacion

    config = config or {}
    separador = config.get("separador", ",")
    encoding = config.get("encoding", "utf-8")
    fmt_fecha = config.get("formato_fecha", "DD/MM/YYYY")

    # Obtener mapeo de cuentas:
    # 1) config["mapeo_cuentas_export"] (pasado por el llamador, ej. del endpoint que ya lo leyó)
    # 2) fallback: Organizacion.configuracion["mapeo_cuentas_export"] en DB
    if "mapeo_cuentas_export" in config:
        mapeo: dict = config["mapeo_cuentas_export"] or {}
    else:
        org = db.query(Organizacion).filter(Organizacion.id == org_id).first()
        mapeo = {}
        if org and isinstance(org.configuracion, dict):
            mapeo = org.configuracion.get("mapeo_cuentas_export", {})

    # Query asientos + detalles + cuentas
    q = (
        db.query(Asiento)
        .filter(Asiento.organizacion_id == org_id)
    )
    if desde:
        q = q.filter(Asiento.fecha >= desde)
    if hasta:
        q = q.filter(Asiento.fecha <= hasta)

    asientos = q.order_by(Asiento.fecha, Asiento.numero_asiento, Asiento.id).all()

    if not asientos:
        # Devolver archivo vacío con cabecera
        filas = []
    else:
        # Batch fetch detalles + cuentas
        asiento_ids = [a.id for a in asientos]
        detalles = (
            db.query(AsientoDetalle, PlanCuenta)
            .join(PlanCuenta, AsientoDetalle.cuenta_id == PlanCuenta.id)
            .filter(AsientoDetalle.asiento_id.in_(asiento_ids))
            .all()
        )
        # Agrupar detalles por asiento
        det_por_asiento: dict[int, list] = {a.id: [] for a in asientos}
        for det, pc in detalles:
            det_por_asiento[det.asiento_id].append((det, pc))

        # Construir filas genéricas: una por cada línea de detalle
        filas = []
        for a in asientos:
            numero = a.numero_asiento or a.id
            for det, pc in det_por_asiento.get(a.id, []):
                codigo_cuadra = pc.codigo
                codigo_exportado = mapeo.get(codigo_cuadra, codigo_cuadra)
                filas.append({
                    "fecha": a.fecha,
                    "numero_asiento": numero,
                    "codigo_cuenta_cuadra": codigo_cuadra,
                    "codigo_cuenta": codigo_exportado,
                    "nombre_cuenta": pc.nombre,
                    "debe": Decimal(str(det.debe or "0")),
                    "haber": Decimal(str(det.haber or "0")),
                    "descripcion": a.descripcion or "",
                })

    # Detectar cuentas sin mapeo (solo relevante para formatos no-csv)
    cuentas_sin_mapeo: list[str] = []
    if formato != "csv" and mapeo:
        cuentas_presentes = {f["codigo_cuenta_cuadra"] for f in filas}
        cuentas_sin_mapeo = sorted([c for c in cuentas_presentes if c not in mapeo])
    elif formato != "csv" and not mapeo:
        # Sin mapeo configurado no advertimos — todos los códigos son los de Cuadra
        cuentas_sin_mapeo = []

    # ── Generar según formato ──────────────────────────────────────────────────
    if formato == "csv":
        content, filename, ct = _export_csv(filas, separador, encoding, fmt_fecha, config)
    elif formato == "tango":
        content, filename, ct = _export_tango(filas, fmt_fecha)
    elif formato == "holistor":
        content, filename, ct = _export_holistor(filas)
    elif formato == "regisoft":
        content, filename, ct = _export_regisoft(filas)
    else:
        raise ValueError(f"Formato desconocido: {formato}")

    return content, filename, ct, cuentas_sin_mapeo


# ── Implementaciones por formato ─────────────────────────────────────────────

def _export_csv(filas, separador, encoding, fmt_fecha, config):
    """CSV genérico: columnas configurables según config["columnas"]."""
    columnas_default = [
        "fecha", "numero_asiento", "codigo_cuenta",
        "nombre_cuenta", "debe", "haber", "descripcion"
    ]
    columnas = config.get("columnas", columnas_default)

    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=separador, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    writer.writerow(columnas)

    for f in filas:
        row = []
        for col in columnas:
            if col == "fecha":
                row.append(_fmt_fecha(f["fecha"], fmt_fecha))
            elif col == "numero_asiento":
                row.append(str(f["numero_asiento"]))
            elif col == "codigo_cuenta":
                row.append(f["codigo_cuenta"])
            elif col == "nombre_cuenta":
                row.append(f["nombre_cuenta"])
            elif col == "debe":
                row.append(_fmt_monto(f["debe"]))
            elif col == "haber":
                row.append(_fmt_monto(f["haber"]))
            elif col == "descripcion":
                row.append(f["descripcion"])
            else:
                row.append("")
        writer.writerow(row)

    content = buf.getvalue().encode(encoding, errors="replace")
    ext = "csv"
    ct = "text/csv; charset=" + encoding
    from datetime import date as _date
    hoy = _date.today().strftime("%Y%m%d")
    filename = f"libro_diario_{hoy}.{ext}"
    return content, filename, ct


def _export_tango(filas, fmt_fecha):
    """Tango Gestión: TXT tab-separated, fecha DD/MM/YYYY, montos con coma decimal.

    Estructura (sin header): FECHA\tNRO\tCUENTA\tDEBE\tHABER\tLEYENDA
    """
    lines = []
    for f in filas:
        fecha = _fmt_fecha(f["fecha"], "DD/MM/YYYY")
        debe = _fmt_monto(f["debe"], coma_decimal=True)
        haber = _fmt_monto(f["haber"], coma_decimal=True)
        parts = [
            fecha,
            str(f["numero_asiento"]),
            f["codigo_cuenta"],
            debe,
            haber,
            f["descripcion"],
        ]
        lines.append("\t".join(parts))

    content = "\r\n".join(lines).encode("latin-1", errors="replace")
    from datetime import date as _date
    hoy = _date.today().strftime("%Y%m%d")
    filename = f"libro_diario_tango_{hoy}.txt"
    ct = "text/plain; charset=latin-1"
    return content, filename, ct


def _export_holistor(filas):
    """Holistor: TXT con estructura fecha;cuenta;debe;haber;leyenda

    Montos con coma decimal, separador punto y coma.
    """
    lines = []
    for f in filas:
        fecha = _fmt_fecha(f["fecha"], "DD/MM/YYYY")
        debe = _fmt_monto(f["debe"], coma_decimal=True)
        haber = _fmt_monto(f["haber"], coma_decimal=True)
        leyenda = f["descripcion"].replace(";", ",")  # escapar separador
        parts = [fecha, f["codigo_cuenta"], debe, haber, leyenda]
        lines.append(";".join(parts))

    content = "\r\n".join(lines).encode("latin-1", errors="replace")
    from datetime import date as _date
    hoy = _date.today().strftime("%Y%m%d")
    filename = f"libro_diario_holistor_{hoy}.txt"
    ct = "text/plain; charset=latin-1"
    return content, filename, ct


def _export_regisoft(filas):
    """Regisoft: CSV con headers Fecha,Cuenta,Detalle,Debe,Haber

    Separador coma, punto decimal, fecha DD/MM/YYYY.
    """
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=",", quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    writer.writerow(["Fecha", "Cuenta", "Detalle", "Debe", "Haber"])

    for f in filas:
        writer.writerow([
            _fmt_fecha(f["fecha"], "DD/MM/YYYY"),
            f["codigo_cuenta"],
            f["descripcion"],
            _fmt_monto(f["debe"]),
            _fmt_monto(f["haber"]),
        ])

    content = buf.getvalue().encode("utf-8")
    from datetime import date as _date
    hoy = _date.today().strftime("%Y%m%d")
    filename = f"libro_diario_regisoft_{hoy}.csv"
    ct = "text/csv; charset=utf-8"
    return content, filename, ct

"""Orquestador: `leer_extracto_pdf` (Contrato 1). Puro: no toca la base.

Embudo (igual que el de planillas):

1. Texto + geometría (`texto.py`). Escaneado → directo a la IA.
2. Capa **molde**: formatos aprendidos de la organización cuya firma aparece en
   el PDF. Se acepta si lee ≥1 fila y el saldo cierra.
3. Capa **automática**: encabezado de columnas reconocido por palabras clave
   y, si no alcanza, lectura estructural (fechas + importes alineados).
4. Capa **IA**: si no se leyó nada, si no cierra o si la persona lo pidió.
   Sin IA configurada queda la lectura automática con una alerta.
5. Siempre: `validar_saldos` sobre el resultado elegido y marcado de filas dudosas.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional, Sequence

from app.services.tz import hoy_art

from . import ia
from .bancos import GENERICO, detectar_banco_texto, detectar_banco_zonas
from .fechas import ContextoFechas, armar_contexto, detectar_periodo, fechas_completas_en
from .molde import aprendizaje_de, firmas_del_documento, inducir_layout, layout_valido, mismas_filas
from .saldos import formatear_pesos, marcar_dudosas, validar_saldos
from .tabla import (
    MOTIVO_DOBLE,
    MOTIVO_FUERA_PERIODO,
    MOTIVO_SIGNO,
    MOTIVO_SIGNO_IMPRESO,
    MOTIVO_SIN_FECHA,
    MOTIVO_VARIOS,
    LecturaTabla,
    detectar_orden,
    fecha_al_inicio,
    layouts_estructurales,
    layouts_por_encabezado,
    leer_con_layout,
    lineas_repetidas,
    tiene_importe,
)
from .texto import Documento, extraer_documento


@dataclass
class _Candidato:
    metodo: str
    filas: list[dict]
    orden: str
    saldo_inicial: Optional[Decimal]
    saldo_final: Optional[Decimal]
    cuadre: dict = field(default_factory=dict)
    molde_id: Optional[int] = None
    aprendizaje: Optional[dict] = None
    periodo: Optional[tuple[date, date]] = None
    banco_texto: Optional[str] = None
    signo: str = "columnas"
    filas_sin_anio: int = 0
    otras_cuentas: bool = False
    renglones_ilegibles: list[int] = field(default_factory=list)
    _interno: Optional[dict] = field(default=None, repr=False)

    @property
    def cierra(self) -> bool:
        """Cierra y no quedaron renglones de la tabla sin leer."""
        return bool(self.cuadre.get("cierra")) and not self.renglones_ilegibles

    def validar(self) -> "_Candidato":
        self.cuadre = validar_saldos(
            self.filas, orden=self.orden, saldo_inicial=self.saldo_inicial, saldo_final=self.saldo_final
        )
        return self

    def puntaje(self) -> tuple:
        """Mejor: con filas > cierra > menor diferencia > más filas > menos saltos."""
        dif = self.cuadre.get("diferencia")
        return (
            bool(self.filas),
            self.cierra,
            dif is not None,
            -abs(dif) if dif is not None else Decimal("0"),
            len(self.filas),
            -len(self.cuadre.get("filas_con_salto") or []),
        )

    @property
    def interno(self) -> dict:
        """El cuadre de los movimientos entre sí, sin los saldos inicial y final del PDF."""
        if self._interno is None:
            self._interno = validar_saldos(self.filas, orden=self.orden, saldo_inicial=None, saldo_final=None)
        return self._interno

    def puntaje_lectura(self) -> tuple:
        """Entre dos lecturas de las mismas filas que no cierran: primero la que sigue
        mejor el saldo fila a fila, después la que menos signos tuvo que suponer (uno
        deducido contra un saldo inicial mal impreso puede achicar la diferencia sin
        ser el bueno; el que dice el PDF, no) y recién después la diferencia."""
        p = self.puntaje()
        saltos = len(self.interno.get("filas_con_salto") or [])
        supuestos = sum(1 for f in self.filas if MOTIVO_SIGNO in (f.get("motivos") or []))
        return p[:3] + (-saltos, -supuestos) + p[3:]


def _mismas_filas(a: _Candidato, b: _Candidato) -> bool:
    def claves(c: _Candidato) -> Counter:
        return Counter((f.get("fecha"), abs(f["monto"])) for f in c.filas)
    return claves(a) == claves(b)


def _gana(nuevo: _Candidato, actual: Optional[_Candidato]) -> bool:
    """Para elegir entre layouts. Con filas distintas, o si alguna cierra, manda el
    puntaje de siempre (más filas leídas, menor diferencia); entre lecturas de las
    mismas filas que no cierran, `puntaje_lectura`."""
    if actual is None:
        return True
    if nuevo.cierra or actual.cierra or not _mismas_filas(nuevo, actual):
        return nuevo.puntaje() > actual.puntaje()
    return nuevo.puntaje_lectura() > actual.puntaje_lectura()


def _alerta(nivel: str, codigo: str, mensaje: str) -> dict:
    return {"nivel": nivel, "codigo": codigo, "mensaje": mensaje}


def _desde_lectura(metodo: str, lectura: LecturaTabla) -> _Candidato:
    return _Candidato(
        metodo=metodo,
        filas=lectura.filas,
        orden=lectura.orden,
        saldo_inicial=lectura.saldo_inicial,
        saldo_final=lectura.saldo_final,
        signo=lectura.signo,
        filas_sin_anio=lectura.filas_sin_anio,
        otras_cuentas=lectura.otras_cuentas,
        renglones_ilegibles=list(lectura.renglones_ilegibles),
    ).validar()


def _detectar_banco(doc: Documento, repetidas: set[int]) -> str:
    """El membrete manda: primero la parte de arriba de la página 1 y las líneas
    que se repiten en todas las páginas; el resto de la página 1 solo si ahí no
    aparece ningún banco. De la página 1 se mira solo lo que está antes del
    primer movimiento: las descripciones ("DESDE BANCO GALICIA CBU …") y sus
    renglones de continuación nombran a otros bancos."""
    membrete: list[tuple[str, float]] = []
    resto: list[tuple[str, float]] = []
    vistas: set[str] = set()
    tabla_empezo = False
    for ln in doc.lineas:
        if tiene_importe(ln) and fecha_al_inicio(ln)[0] is not None:
            tabla_empezo = tabla_empezo or ln.pagina == 1
            continue                                   # parece un movimiento
        if id(ln) in repetidas:
            if ln.texto not in vistas:
                vistas.add(ln.texto)
                membrete.append((ln.texto, 2.0))
        elif ln.pagina == 1 and not tabla_empezo:
            if ln.altura_relativa >= 0.7:
                membrete.append((ln.texto, 3.0))
            else:
                resto.append((ln.texto, 1.0))
    banco = detectar_banco_zonas(membrete)
    return banco if banco != GENERICO else detectar_banco_zonas(resto)


def _capa_moldes(
    doc: Documento, moldes: Sequence[dict], banco: str, ctx: ContextoFechas, repetidas: set[int], alertas: list
) -> Optional[_Candidato]:
    if not moldes:
        return None
    firmas = firmas_del_documento(doc, banco)
    probo = False
    for molde in moldes:
        if not isinstance(molde, dict) or molde.get("firma") not in firmas:
            continue
        clave = molde.get("banco_clave")
        if clave and clave != banco and banco != GENERICO:
            continue
        layout = molde.get("layout")
        if not layout_valido(layout):
            continue
        probo = True
        cand = _desde_lectura("molde", leer_con_layout(doc, layout, ctx, repetidas))
        if cand.filas and cand.cierra:
            cand.molde_id = molde.get("id")
            return cand
    if probo:
        alertas.append(_alerta(
            "info", "molde_no_cierra",
            "El formato aprendido de este banco no cerró con este PDF: se leyó de nuevo desde cero.",
        ))
    return None


def _capa_automatica(doc: Documento, banco: str, ctx: ContextoFechas, repetidas: set[int]) -> Optional[_Candidato]:
    mejor: Optional[_Candidato] = None
    mejor_layout: Optional[dict] = None
    for layout in layouts_por_encabezado(doc):
        cand = _desde_lectura("automatico", leer_con_layout(doc, layout, ctx, repetidas))
        if _gana(cand, mejor):
            mejor, mejor_layout = cand, layout
    if mejor is None or not (mejor.filas and mejor.cierra):
        for layout in layouts_estructurales(doc, repetidas):
            cand = _desde_lectura("automatico", leer_con_layout(doc, layout, ctx, repetidas))
            if _gana(cand, mejor):
                mejor, mejor_layout = cand, layout
    if mejor is not None and mejor.filas and mejor_layout is not None:
        mejor.aprendizaje = aprendizaje_de(mejor_layout, banco)
    return mejor


def _capa_ia(
    doc: Documento, contenido: bytes, banco: str, ctx: ContextoFechas, repetidas: set[int], alertas: list
) -> tuple[Optional[_Candidato], bool]:
    resultado, alertas_ia, usada = ia.leer_con_ia(doc, contenido, ctx, escaneado=doc.escaneado)
    alertas.extend(alertas_ia)
    if not resultado or not resultado["movimientos"]:
        return None, usada
    filas = [
        {**m, "pagina": None, "dudosa": False, "motivos": []}
        for m in resultado["movimientos"]
    ]
    orden = detectar_orden(
        [f["fecha"] for f in filas], [f["monto"] for f in filas], [f["saldo"] for f in filas],
        resultado["saldo_inicial"],
    )
    cand = _Candidato(
        metodo="ia",
        filas=filas,
        orden=orden,
        saldo_inicial=resultado["saldo_inicial"],
        saldo_final=resultado["saldo_final"],
        periodo=resultado["periodo"],
        banco_texto=resultado["banco"],
    ).validar()
    for f in cand.filas:
        if f["fecha"] is None:
            f["motivos"].append(MOTIVO_SIN_FECHA)
        elif ctx.periodo and not (
            ctx.periodo[0] - timedelta(days=7) <= f["fecha"] <= ctx.periodo[1] + timedelta(days=7)
        ):
            f["motivos"].append(MOTIVO_FUERA_PERIODO)
        f["dudosa"] = bool(f["motivos"])
    if not doc.escaneado:
        layout = inducir_layout(doc, cand.filas, repetidas)
        if layout is not None:
            relectura = leer_con_layout(doc, layout, ctx, repetidas)
            if mismas_filas(relectura.filas, cand.filas):
                cand.aprendizaje = aprendizaje_de(layout, banco)
    return cand, usada


def leer_extracto_pdf(
    contenido: bytes,
    *,
    moldes: Sequence[dict] = (),
    usar_ia: bool = True,
    forzar_ia: bool = False,
    hoy: Optional[date] = None,
) -> dict:
    """Lee un extracto bancario en PDF. Ver el contrato en el docstring del paquete.

    Lanza `ExtractoPdfError` solo si el archivo no se puede abrir (no es PDF,
    dañado, con contraseña, demasiadas páginas)."""
    hoy = hoy or hoy_art()
    doc = extraer_documento(contenido)
    alertas: list[dict] = []
    repetidas = lineas_repetidas(doc)
    banco = _detectar_banco(doc, repetidas)
    periodo = detectar_periodo(
        [ln.texto for ln in doc.lineas if ln.pagina <= 2 and not tiene_importe(ln)]
    )
    fechas_doc = [f for ln in doc.lineas for f in fechas_completas_en(ln.texto)] if not periodo else []
    ctx = armar_contexto(periodo, fechas_doc, hoy)
    clave_ia = ia.ia_disponible()
    ia_disponible = usar_ia and clave_ia

    if doc.escaneado:
        alertas.append(_alerta(
            "info", "escaneado",
            "El PDF no tiene texto seleccionable (parece escaneado o una foto): hace falta leerlo con IA.",
        ))
    if doc.paginas_ilegibles:
        paginas = ", ".join(str(p) for p in doc.paginas_ilegibles)
        alertas.append(_alerta("aviso", "paginas_ilegibles", f"No se pudieron leer las páginas: {paginas}."))

    deterministico: Optional[_Candidato] = None
    if not doc.escaneado:
        if not forzar_ia or not ia_disponible:
            deterministico = _capa_moldes(doc, moldes, banco, ctx, repetidas, alertas)
            if deterministico is None:
                deterministico = _capa_automatica(doc, banco, ctx, repetidas)

    det_ok = deterministico is not None and bool(deterministico.filas) and deterministico.cierra
    necesita_ia = forzar_ia or doc.escaneado or not det_ok
    elegido = deterministico
    ia_usada = False
    if necesita_ia and ia_disponible:
        con_ia, ia_usada = _capa_ia(doc, contenido, banco, ctx, repetidas, alertas)
        if forzar_ia and con_ia is not None:
            elegido = con_ia
        elif forzar_ia and con_ia is None and deterministico is None and not doc.escaneado:
            # La IA falló y se había salteado la lectura automática: hacerla igual.
            deterministico = _capa_moldes(doc, moldes, banco, ctx, repetidas, alertas) or _capa_automatica(
                doc, banco, ctx, repetidas
            )
            elegido = deterministico
        elif con_ia is not None and (elegido is None or con_ia.puntaje() > elegido.puntaje()):
            elegido = con_ia
    elif necesita_ia and not clave_ia:
        # Con clave pero usar_ia=False, quien llama corre la IA después (en segundo plano).
        alertas.append(_alerta(
            "aviso", "ia_no_disponible",
            "La lectura con IA no está configurada en el servidor: revisá los movimientos a mano"
            + (" o cargalos uno por uno." if doc.escaneado else "."),
        ))

    return _armar_salida(doc, elegido, banco, periodo, ctx, alertas, ia_usada, ia_disponible)


def _armar_salida(
    doc: Documento,
    elegido: Optional[_Candidato],
    banco: str,
    periodo: Optional[tuple[date, date]],
    ctx: ContextoFechas,
    alertas: list[dict],
    ia_usada: bool,
    ia_disponible: bool,
) -> dict:
    if elegido is None:
        elegido = _Candidato(metodo="", filas=[], orden="asc", saldo_inicial=None, saldo_final=None).validar()
    filas = marcar_dudosas(elegido.filas, elegido.cuadre)
    for f in filas:
        f["motivos"] = list(dict.fromkeys(f.get("motivos") or []))
        f["dudosa"] = bool(f.get("dudosa") or f["motivos"])
    cuadre = elegido.cuadre

    if banco == GENERICO and elegido.banco_texto:
        banco = detectar_banco_texto(elegido.banco_texto)
    if periodo is None:
        periodo = elegido.periodo
    if periodo is None:
        fechas = [f["fecha"] for f in filas if f.get("fecha")]
        if fechas:
            periodo = (min(fechas), max(fechas))

    if not filas:
        alertas.append(_alerta(
            "error", "sin_movimientos",
            "No se encontraron movimientos en el PDF. Podés cargarlos a mano o descartar el archivo.",
        ))
    else:
        hay_saldos = any(f.get("saldo") is not None for f in filas)
        saltos = len(cuadre.get("filas_con_salto") or [])
        if cuadre["diferencia"] is None:
            if not hay_saldos and cuadre["saldo_inicial"] is None and cuadre["saldo_final"] is None:
                alertas.append(_alerta(
                    "aviso", "sin_saldos",
                    "El PDF no muestra saldos: no se pudo comprobar que el extracto cierre. Revisá los totales.",
                ))
            elif cuadre["saldo_inicial"] is None:
                alertas.append(_alerta(
                    "aviso", "sin_saldo_inicial",
                    "No se encontró el saldo inicial: cargalo para comprobar que el extracto cierre.",
                ))
            else:
                alertas.append(_alerta(
                    "aviso", "sin_saldo_final",
                    "No se encontró el saldo final y el último movimiento no trae saldo: cargalo para "
                    "comprobar que el extracto cierre.",
                ))
        elif not cuadre["cierra"]:
            # El aviso "borrá ese saldo" solo con una lectura completa del texto del
            # PDF: si faltan hojas o renglones, o leyó la IA, el saldo del PDF puede
            # estar bien y lo que falta es un movimiento.
            incompleta = bool(
                elegido.renglones_ilegibles or doc.paginas_ilegibles or doc.paginas_sin_texto
                or elegido.otras_cuentas or elegido.metodo == "ia"
            )
            encabezado = None if incompleta else _saldos_del_pdf_que_no_coinciden(
                filas, elegido.orden, cuadre, signo_del_pdf=elegido.signo in ("columnas", "explicito")
            )
            if encabezado:
                mensaje = encabezado
            elif saltos and abs(cuadre["diferencia"]) <= Decimal("0.01"):
                mensaje = (
                    f"Los totales dan, pero el saldo no sigue en {saltos} "
                    f"{'movimiento' if saltos == 1 else 'movimientos'}: revisá los marcados."
                )
            else:
                mensaje = f"El saldo no cierra: hay una diferencia de {formatear_pesos(cuadre['diferencia'])}."
            alertas.append(_alerta("aviso", "no_cierra", mensaje))
        sin_texto = [p for p in doc.paginas_sin_texto if p not in doc.paginas_ilegibles]
        if sin_texto and not cuadre["cierra"] and not doc.escaneado:
            paginas = ", ".join(str(p) for p in sin_texto)
            alertas.append(_alerta(
                "aviso", "paginas_sin_texto",
                f"{'La página' if len(sin_texto) == 1 else 'Las páginas'} {paginas} casi no "
                f"{'tiene' if len(sin_texto) == 1 else 'tienen'} texto para leer (puede ser una imagen o una "
                "hoja girada): fijate en el PDF si falta algún movimiento y cargalo a mano.",
            ))
        if elegido.renglones_ilegibles:
            n = len(elegido.renglones_ilegibles)
            paginas = ", ".join(str(p) for p in sorted(set(elegido.renglones_ilegibles)))
            alertas.append(_alerta(
                "aviso", "renglones_ilegibles",
                f"{'Hay un renglón' if n == 1 else f'Hay {n} renglones'} con fecha que no se "
                f"{'pudo' if n == 1 else 'pudieron'} leer (página {paginas}): fijate en el PDF si falta "
                "algún movimiento y cargalo a mano.",
            ))
        dudosas = sum(1 for f in filas if f["dudosa"])
        if dudosas:
            alertas.append(_alerta(
                "aviso", "filas_dudosas",
                f"Hay {dudosas} movimiento{'s' if dudosas != 1 else ''} para revisar (marcados en amarillo).",
            ))
        if elegido.signo == "saldo":
            alertas.append(_alerta(
                "info", "signo_deducido",
                "El PDF no separa débitos de créditos: el signo de cada movimiento se dedujo del saldo.",
            ))
        if elegido.otras_cuentas:
            alertas.append(_alerta(
                "aviso", "varias_cuentas",
                "El PDF tiene más de una cuenta: se leyó solo la primera. Si necesitás otra, "
                "descargá el resumen de esa cuenta por separado.",
            ))
        if elegido.filas_sin_anio and ctx.origen == "hoy":
            alertas.append(_alerta(
                "info", "anio_supuesto",
                "Las fechas del PDF no traen año y no figura el período: se tomó el año más reciente. Revisalas.",
            ))

    salida_filas = [
        {
            "fecha": f.get("fecha"),
            "descripcion": f.get("descripcion") or "",
            "monto": f["monto"],
            "saldo": f.get("saldo"),
            "pagina": f.get("pagina"),
            "dudosa": f["dudosa"],
            "motivos": f["motivos"],
        }
        for f in filas
    ]
    return {
        "metodo": elegido.metodo or None,
        "molde_id": elegido.molde_id if elegido.metodo == "molde" else None,
        "banco_clave": banco,
        "paginas": doc.paginas,
        "escaneado": doc.escaneado,
        "orden": elegido.orden,
        "periodo_desde": periodo[0] if periodo else None,
        "periodo_hasta": periodo[1] if periodo else None,
        "saldo_inicial": cuadre["saldo_inicial"],
        "saldo_final": cuadre["saldo_final"],
        "movimientos": salida_filas,
        "cuadre": cuadre,
        "alertas": _sin_repetidas(alertas),
        "aprendizaje": elegido.aprendizaje if elegido.metodo in ("automatico", "ia") else None,
        "ia_usada": ia_usada,
        "ia_disponible": ia_disponible,
    }


def _saldos_del_pdf_que_no_coinciden(
    filas: list[dict], orden: str, cuadre: dict, *, signo_del_pdf: bool
) -> Optional[str]:
    """Si los movimientos cierran entre sí y lo que no coincide es el saldo inicial o
    final que figura en el PDF, el mensaje que lo dice (falta una hoja o el cuadro de
    arriba trae otro saldo). Solo con dos movimientos o más, todos con su saldo (así
    cada uno se controla contra el anterior) y sin dudas en ninguna fila: si un
    signo se supuso, el saldo "de los movimientos" es el dudoso; y una fecha fuera
    del período puede ser un movimiento que no va. Del lado del saldo inicial además
    hace falta que el signo lo diga el PDF (deducido, se eligió para llegar a ese
    saldo)."""
    dudas = (MOTIVO_SIGNO, MOTIVO_SIGNO_IMPRESO, MOTIVO_DOBLE, MOTIVO_VARIOS, MOTIVO_SIN_FECHA, MOTIVO_FUERA_PERIODO)
    if (
        len(filas) < 2
        or any(f.get("saldo") is None for f in filas)
        or any(m in (f.get("motivos") or []) for f in filas for m in dudas)
    ):
        return None
    interno = validar_saldos(filas, orden=orden, saldo_inicial=None, saldo_final=None)
    if not interno["cierra"]:
        return None
    lados = [("saldo_final", "final")]
    if signo_del_pdf:
        lados.insert(0, ("saldo_inicial", "inicial"))
    partes = []
    for clave, nombre in lados:
        del_pdf, de_filas = cuadre[clave], interno[clave]
        if (
            not cuadre[f"{clave}_inferido"]
            and del_pdf is not None
            and de_filas is not None
            and abs(del_pdf - de_filas) > Decimal("0.01")
        ):
            partes.append(
                f"el saldo {nombre} que figura en el PDF ({formatear_pesos(del_pdf)}) no coincide con el "
                f"que sale de los movimientos ({formatear_pesos(de_filas)})"
            )
    if not partes:
        return None
    return (
        "Los movimientos cierran entre sí, pero " + " y ".join(partes) + ". Fijate que no falte ninguna "
        "hoja ni ningún movimiento; si está todo, "
        + ("borrá ese saldo y se usa el" if len(partes) == 1 else "borrá esos saldos y se usan los")
        + " de los movimientos."
    )


def _sin_repetidas(alertas: list[dict]) -> list[dict]:
    vistas: set[str] = set()
    out = []
    for a in alertas:
        if a["codigo"] in vistas:
            continue
        vistas.add(a["codigo"])
        out.append(a)
    return out

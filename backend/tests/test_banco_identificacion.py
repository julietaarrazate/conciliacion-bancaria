"""Reconocer el banco de un extracto (`services/banco_identificacion.py`).

Los CBU/CVU y números de cuenta son ficticios: se arman con `cbu_ficticio`, que
calcula los dos dígitos verificadores, así pasan la validación sin ser de nadie.
"""

from app.services import banco_identificacion as bi

PESOS1 = (7, 1, 3, 9, 7, 1, 3)
PESOS2 = (3, 9, 7, 1, 3, 9, 7, 1, 3, 9, 7, 1, 3)


def _dv(digitos: str, pesos) -> str:
    return str((10 - sum(int(d) * p for d, p in zip(digitos, pesos)) % 10) % 10)


def cbu_ficticio(entidad: str, sucursal: str = "0999", cuenta: str = "0000012345678") -> str:
    b1 = entidad + sucursal
    return b1 + _dv(b1, PESOS1) + cuenta + _dv(cuenta, PESOS2)


def _romper(cbu: str) -> str:
    """Mismo CBU con el último verificador mal."""
    return cbu[:-1] + str((int(cbu[-1]) + 1) % 10)


# ── Validación del CBU ───────────────────────────────────────────────────────

def test_cbu_valido_con_verificadores():
    c = cbu_ficticio("285")
    assert len(c) == 22 and bi.cbu_valido(c)
    # También con espacios o guiones (como suele imprimirse).
    assert bi.cbu_valido(" ".join([c[:4], c[4:8], c[8:12], c[12:16], c[16:20], c[20:]]))


def test_cbu_invalido():
    c = cbu_ficticio("285")
    assert not bi.cbu_valido(_romper(c))                       # bloque 2 mal
    malo1 = c[:7] + str((int(c[7]) + 1) % 10) + c[8:]
    assert not bi.cbu_valido(malo1)                            # bloque 1 mal
    assert not bi.cbu_valido(c[:-1])                           # 21 dígitos
    assert not bi.cbu_valido("0" * 22)
    assert bi.banco_de_cbu(_romper(c)) is None


def test_codigo_bcra_a_banco():
    esperados = {
        "007": "galicia", "011": "nacion", "014": "provincia", "015": "icbc", "017": "bbva",
        "020": "bancor", "027": "supervielle", "029": "ciudad", "034": "patagonia",
        "044": "hipotecario", "045": "sanjuan", "072": "santander", "093": "lapampa",
        "143": "brubank", "150": "hsbc", "191": "credicoop", "285": "macro", "299": "comafi",
        "309": "rioja", "322": "bind",
    }
    for codigo, clave in esperados.items():
        dato = bi.banco_de_cbu(cbu_ficticio(codigo))
        assert dato and dato[0] == clave and dato[2] == "cbu", codigo
    # Entidad que no está en la tabla → None (no se inventa).
    assert bi.banco_de_cbu(cbu_ficticio("999")) is None


def test_todos_los_bancos_del_parser_tienen_codigo_o_cvu():
    from app.services.excel_parser import INDICADORES_BANCO
    con_cbu = {c for c, _ in bi.BANCOS_POR_CODIGO.values()} | {c for c, _ in bi.CVU_PREFIJOS.values()}
    assert set(INDICADORES_BANCO) <= con_cbu


def test_cvu_mercado_pago():
    cvu = cbu_ficticio("000", "0003", "0000099999999")
    assert cvu.startswith("00000031")  # como los CVU reales de MP
    assert bi.banco_de_cbu(cvu) == ("mercadopago", "Mercado Pago", "cvu")
    r = bi.identificar_banco(textos_encabezado=[f"CVU: {cvu}"])
    assert r["banco_clave"] == "mercadopago"
    assert r["motivo"] == "por el CVU de la cuenta"
    # CVU de otra billetera (prefijo desconocido): no se adivina.
    otro = cbu_ficticio("000", "0079")
    assert bi.banco_de_cbu(otro) is None


def test_cuit_del_banco():
    r = bi.identificar_banco(textos_encabezado=["Emisor CUIT 30-50001008-4", "Resumen de cuenta"])
    assert r["banco_clave"] == "macro" and r["motivo"] == "por el CUIT del banco"
    # Un CUIT con el verificador mal no cuenta.
    assert bi.buscar_cuits_banco("30-50001008-5") == []


# ── Prioridad de las señales ─────────────────────────────────────────────────

def test_cbu_le_gana_a_un_nombre_engañoso():
    cbu = cbu_ficticio("007")                                   # Galicia
    r = bi.identificar_banco(
        textos_encabezado=["Banco Macro - Resumen", f"CBU {cbu}"], por_nombre="macro",
    )
    assert r["banco_clave"] == "galicia"
    assert r["motivo"] == "por el CBU de la cuenta"
    assert r["conflicto"] and "Banco Macro" in r["conflicto"]
    assert r["pedir_confirmacion"] is True


def test_cbu_en_el_nombre_del_archivo():
    cbu = cbu_ficticio("017")
    r = bi.identificar_banco(nombre_archivo=f"movimientos_{cbu}.csv")
    assert r["banco_clave"] == "bbva" and r["confianza"] >= 0.9


def test_cbu_en_metadatos():
    r = bi.identificar_banco(metadatos=[f"Cuenta {cbu_ficticio('191')}"])
    assert r["banco_clave"] == "credicoop"


def test_confirmado_le_gana_a_todo_y_avisa():
    r = bi.identificar_banco(
        textos_encabezado=[f"CBU {cbu_ficticio('285')}"], aprendido="galicia", aprendido_confirmado=True,
    )
    assert r["banco_clave"] == "galicia" and r["motivo"] == "confirmado antes"
    assert r["conflicto"] and "Banco Macro" in r["conflicto"]


def test_aprendido_sin_confirmar_va_debajo_de_la_estructura():
    r = bi.identificar_banco(por_estructura="macro", aprendido="galicia")
    assert r["banco_clave"] == "macro"
    r = bi.identificar_banco(por_nombre="bbva", aprendido="galicia")
    assert r["banco_clave"] == "galicia" and r["motivo"] == "por un archivo igual que ya subiste"


def test_nombre_es_la_señal_más_débil():
    r = bi.identificar_banco(por_nombre="santander")
    assert r["banco_clave"] == "santander"
    assert r["motivo"] == "por el nombre en el encabezado"
    assert r["pedir_confirmacion"] is True                   # 0.55 < mínimo


def test_nombre_de_banco_nuevo_y_del_archivo():
    assert bi.identificar_banco(textos_encabezado=["BRUBANK S.A.U."])["banco_clave"] == "brubank"
    r = bi.identificar_banco(nombre_archivo="Extracto Banco Galicia octubre.xlsx")
    assert r["banco_clave"] == "galicia" and r["motivo"] == "por el nombre del archivo"


def test_banco_industrial_no_es_icbc():
    r = bi.identificar_banco(textos_encabezado=["Banco Industrial S.A."], por_nombre="icbc")
    assert r["banco_clave"] == "bind"


def test_nada_es_generico_con_confianza_baja():
    r = bi.identificar_banco(textos_encabezado=["Resumen de cuenta", "Período 09/2026"])
    assert r["banco_clave"] == "generico"
    assert r["nombre"] is None
    assert r["confianza"] == 0.0
    assert r["pedir_confirmacion"] is True
    assert "elegilo" in r["motivo"]


def test_dos_cbu_de_bancos_distintos_gana_el_mas_repetido():
    a, b = cbu_ficticio("072"), cbu_ficticio("011")
    r = bi.identificar_banco(textos_encabezado=[f"CBU {a}", f"Cuenta {a}", f"Destino {b}"])
    assert r["banco_clave"] == "santander"
    assert "Banco Nación" in (r["conflicto"] or "")


# ── Formato del archivo ──────────────────────────────────────────────────────

def test_estructura_macro_por_encabezados():
    assert bi.banco_por_estructura(["Orden", "Fecha", "Mes", "Titular", "Importe", "Saldo"]) == "macro"
    assert bi.banco_por_estructura(["Fecha", "Concepto", "Débito", "Crédito", "Saldo"]) is None


def test_estructura_mercado_pago_por_columnas():
    filas = [["RELEASE_DATE", "TRANSACTION_TYPE", "TRANSACTION_AMOUNT", "BALANCE_AMOUNT"]]
    assert bi.banco_por_estructura(filas_cabecera=filas) == "mercadopago"


def test_estructura_macro_por_conceptos():
    conceptos = ["ING TRANSF: GOMEZ ANA", "ING. TRANSF: PEREZ", "COMISION"]
    assert bi.banco_por_estructura(conceptos=conceptos) == "macro"
    assert bi.banco_por_estructura(conceptos=["ING TRANSF: UNO"]) is None   # uno solo no alcanza


def test_lista_bancos_para_el_desplegable():
    claves = {b["clave"] for b in bi.lista_bancos()}
    assert {"macro", "galicia", "mercadopago", "brubank", "lapampa"} <= claves
    assert bi.clave_valida("macro") and bi.clave_valida("generico") and not bi.clave_valida("xx")

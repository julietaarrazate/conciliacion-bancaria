"""Tests de scoring del motor de conciliación (`_score_identidad` + `buscar_match`).

DOCUMENTAN el comportamiento ACTUAL del scoring por identidad — no lo cambian.
La Organización A (id=1) depende de este algoritmo tal cual en producción, así que
estos tests son un blindaje de regresión: si alguno cambia de resultado tras un
refactor, el refactor rompió el matcher.

Tabla de puntajes de identidad (ver `_score_identidad`):
    12  CUIT exacto (o CUIT de la planilla como substring de dígitos del mov)
    10  CBU/CVU (22 dígitos) en común
     8  número de cuenta largo (10+ dígitos) en común
     6  número de referencia/operación (6-9 dígitos) en común
     5  titular: 2 primeras palabras en orden exacto
     4  titular: 2 primeras palabras, distinto orden
     3  titular: solo la primera palabra
     0  sin coincidencia de identidad

Todos los tests de `_score_identidad` usan `dias_tolerancia=0` para AISLAR el score
de identidad (sin bonus de fecha).
"""

from app.services.conciliacion import _score_identidad, buscar_match, CONFIG_DEFAULT_ORG
from app.models.extracto import MovimientoBanco


def _mov(monto=5000.0, titular="", cliente_acreditado=None, id=1, fecha=None):
    return MovimientoBanco(
        id=id, extracto_id=1, monto=monto, titular=titular,
        cliente_acreditado=cliente_acreditado, fecha=fecha,
    )


def _score(cuit_plan="", cbu_plan="", titular_plan="", nums=None, mov=None):
    """Score de identidad puro (sin bonus de fecha)."""
    return _score_identidad(cuit_plan, cbu_plan, titular_plan, nums or set(), mov, None, 0)


# ── _score_identidad: identificadores numéricos ───────────────────────────────

class TestScoreIdentidadNumeros:

    def test_cuit_exacto_en_texto_del_movimiento_score_12(self):
        mov = _mov(titular="TRANSF 20112233440 GARCIA MARIA")
        assert _score(cuit_plan="20112233440", mov=mov) == 12

    def test_cuit_planilla_como_substring_de_digitos_formato_guiones_score_12(self):
        """CUIT '20112233440' embebido como '20-11223344-0' en el mov → 12."""
        mov = _mov(titular="PAGO 20-11223344-0 GARCIA")
        assert _score(cuit_plan="20112233440", mov=mov) == 12

    def test_cbu_22_digitos_en_comun_score_10(self):
        cbu = "2850590940090418135201"
        mov = _mov(titular="CBU " + cbu + " EMPRESA SA")
        assert _score(cbu_plan=cbu, nums={cbu}, mov=mov) == 10

    def test_numero_cuenta_largo_10_digitos_en_comun_score_8(self):
        mov = _mov(titular="CTA 1234567890 EMPRESA")
        assert _score(nums={"1234567890"}, mov=mov) == 8

    def test_numero_referencia_corto_6_digitos_en_comun_score_6(self):
        mov = _mov(titular="OPERACION 123456 EMPRESA")
        assert _score(nums={"123456"}, mov=mov) == 6


# ── _score_identidad: titular por palabras ────────────────────────────────────

class TestScoreIdentidadTitular:

    def test_titular_2_palabras_mismo_orden_score_5(self):
        mov = _mov(titular="JUAN GARCIA")
        assert _score(titular_plan="JUAN GARCIA", mov=mov) == 5

    def test_titular_2_palabras_distinto_orden_score_4(self):
        """'GARCIA JUAN' (planilla) vs 'JUAN GARCIA' (mov): ambas presentes, otro orden → 4."""
        mov = _mov(titular="JUAN GARCIA")
        assert _score(titular_plan="GARCIA JUAN", mov=mov) == 4

    def test_titular_solo_primera_palabra_coincide_score_3(self):
        mov = _mov(titular="JUAN GARCIA")
        assert _score(titular_plan="JUAN PEREZ", mov=mov) == 3

    def test_nombres_cortos_no_se_filtran_ana_leo_sol(self):
        """Nombres de 3 letras (Ana, Leo, Sol) SÍ cuentan (umbral len >= 3)."""
        assert _score(titular_plan="ANA", mov=_mov(titular="ANA")) == 3
        assert _score(titular_plan="LEO", mov=_mov(titular="PAGO LEO")) == 3
        assert _score(titular_plan="SOL", mov=_mov(titular="SOL MARTINEZ")) == 3

    def test_titular_presente_pero_mov_es_procesador_no_matchea(self):
        """Caso 'tiene identidad pero el extracto no la trae': la planilla tiene
        titular real (JUAN GARCIA) pero el movimiento del banco muestra el
        procesador ('MERCADO PAGO'), no el pagador → score 0 por identidad."""
        mov = _mov(titular="MERCADO PAGO")
        assert _score(titular_plan="JUAN GARCIA", mov=mov) == 0

    def test_sin_ningun_dato_identificatorio_score_0(self):
        assert _score(mov=_mov(titular="LO QUE SEA")) == 0


# ── buscar_match: reglas de acreditación con la config default ────────────────

class TestBuscarMatchScoring:

    def test_monto_unico_sin_identidad_se_acredita_igual(self):
        """Comportamiento actual: monto que aparece 1 sola vez → se acredita aunque
        NO haya CUIT/CBU/titular (no hay ambigüedad posible)."""
        mov = _mov(5000.0, titular="ALGO INDESCIFRABLE", id=1)
        r, s = buscar_match(5000.0, None, None, None, None, [mov], set(), CONFIG_DEFAULT_ORG)
        assert r is not None and r.id == 1
        assert s == "ok"

    def test_monto_duplicado_cuit_desempata_gana_score_12(self):
        movs = [
            _mov(5000.0, titular="EMPRESA A 20111111110", id=1),
            _mov(5000.0, titular="OTRA B 27222222220", id=2),
        ]
        r, s = buscar_match(5000.0, "20111111110", None, None, None, movs, set(), CONFIG_DEFAULT_ORG)
        assert r is not None and r.id == 1
        assert s == "ok"

    def test_monto_duplicado_empate_score_bajo_menor_a_5_es_ambiguo(self):
        """Dos candidatos que empatan con score < 5 (solo primera palabra, 3) →
        no se arriesga: resultado ambiguo, no acredita."""
        movs = [
            _mov(5000.0, titular="JUAN GARCIA", id=1),
            _mov(5000.0, titular="JUAN LOPEZ", id=2),
        ]
        r, s = buscar_match(5000.0, None, "JUAN PEREZ", None, None, movs, set(), CONFIG_DEFAULT_ORG)
        assert r is None
        assert "ambiguo" in s

    def test_monto_duplicado_empate_score_alto_5_no_se_marca_ambiguo(self):
        """COMPORTAMIENTO ACTUAL (posible punto a calibrar): un empate con score
        >= 5 (ambos matchean las 2 palabras en orden) NO se marca ambiguo y se
        acredita al PRIMERO silenciosamente. El guard de ambigüedad solo aplica a
        empates con score < 5."""
        movs = [
            _mov(5000.0, titular="JUAN GARCIA", id=1),
            _mov(5000.0, titular="JUAN GARCIA", id=2),
        ]
        r, s = buscar_match(5000.0, None, "JUAN GARCIA", None, None, movs, set(), CONFIG_DEFAULT_ORG)
        assert r is not None and r.id == 1
        assert s == "ok"

    def test_monto_duplicado_sin_ningun_dato_reporta_sin_datos(self):
        movs = [
            _mov(5000.0, titular="A 20111111110", id=1),
            _mov(5000.0, titular="B 27222222220", id=2),
        ]
        r, s = buscar_match(5000.0, None, None, None, None, movs, set(), CONFIG_DEFAULT_ORG)
        assert r is None
        assert "sin datos" in s

    def test_monto_duplicado_procesadores_no_acredita_por_titular(self):
        """Caso 'tiene identidad pero el extracto no la trae' a nivel buscar_match:
        planilla con titular real pero ambos movimientos del mismo monto son
        procesadores ('MERCADO PAGO') → no coincide (no se acredita al azar)."""
        movs = [
            _mov(5000.0, titular="MERCADO PAGO", id=1),
            _mov(5000.0, titular="MERCADO PAGO", id=2),
        ]
        r, s = buscar_match(5000.0, None, "JUAN GARCIA", None, None, movs, set(), CONFIG_DEFAULT_ORG)
        assert r is None
        assert "no coincide" in s

"""
Resolución de OT y tarea (docs/ai/14-resolucion-ot.md, iteración 1).
Funciones puras: sin dobles de BD. Comportamiento nuevo (no es caracterización).
"""
import pytest

from services.resolucion_ot_service import evaluar_elegibilidad_op, resolver


# ---------------------------------------------------------------- elegibilidad

def _job(status="N", state="N", locked="0"):
    return {"j_number": "51847", "j_status": status, "j_state": state,
            "j_locked": locked, "j_title1": "Revista"}


@pytest.mark.parametrize("status, state, locked, codigo", [
    ("X", "N", "0", "OP_CANCELADA"),
    ("X", "S", "1", "OP_CANCELADA"),            # el orden importa: cancelada gana
    (None, "N", "0", "OP_COMPLETITUD_DESCONOCIDA"),
    ("Z", "N", "0", "OP_COMPLETITUD_DESCONOCIDA"),
    ("n", "N", "0", "OP_COMPLETITUD_DESCONOCIDA"),  # no se cambian mayúsculas
    ("N", "R", "0", "OP_RESERVADA"),
    ("N", "S", "1", "OP_SUSPENDIDA"),           # j_state antes que j_locked
    ("N", None, "0", "OP_ESTADO_DESCONOCIDO"),
    ("N", "Q", "0", "OP_ESTADO_DESCONOCIDO"),
    ("N", "N", "1", "OP_BLOQUEADA"),
    ("N", "N", 1, "OP_BLOQUEADA"),
    ("N", "N", None, "OP_BLOQUEO_DESCONOCIDO"),
    ("N", "N", "2", "OP_BLOQUEO_DESCONOCIDO"),
    ("N", "N", "0", "OP_ELEGIBLE"),
    ("C", "N", "0", "OP_ELEGIBLE"),
    (" N ", " N ", 0, "OP_ELEGIBLE"),           # strip y j_locked entero
])
def test_elegibilidad(status, state, locked, codigo):
    resultado = evaluar_elegibilidad_op(_job(status, state, locked))
    assert resultado["codigo"] == codigo
    assert resultado["ok"] is (codigo == "OP_ELEGIBLE")
    assert resultado["mensaje"]


@pytest.mark.parametrize("fila", [None, [], {"j_status": "N", "j_state": "N"}])
def test_elegibilidad_entrada_defectuosa(fila):
    with pytest.raises(ValueError):
        evaluar_elegibilidad_op(fila)


# ---------------------------------------------------------------- resolver

def _ot(numero, seq=None, status="N", titulo=None):
    return {"wo_number": numero, "wo_status": status, "wo_seq": seq, "wo_title2": titulo}


def _tarea(tk_id, wonum, seq=1, status="N"):
    return {"tk_id": tk_id, "tk_wonum": wonum, "tk_status": status, "tk_seq": seq}


def test_sin_candidatas_es_sin_tarea():
    r = resolver([_ot("5184701", 1)], [])
    assert r["ok"] and r["estado"] == "SIN_TAREA"
    assert (r["wo_number"], r["tk_id"], r["titulo_ot"]) == (None, None, None)
    assert r["num_candidatas"] == 0 and r["ot_elegida"] is False


def test_una_candidata_es_automatica():
    r = resolver([_ot("5184701", 1, titulo="Tripa")], [_tarea(10, "5184701")])
    assert r["ok"] and r["estado"] == "AUTOMATICA"
    assert (r["wo_number"], r["tk_id"], r["titulo_ot"]) == ("5184701", 10, "Tripa")
    assert r["ot_elegida"] is False


@pytest.mark.parametrize("elegida", ["5184701", 5184701])
def test_una_candidata_con_eleccion_coincidente_sigue_automatica(elegida):
    r = resolver([_ot("5184701", 1)], [_tarea(10, "5184701")], ot_elegida=elegida)
    assert r["estado"] == "AUTOMATICA" and r["ot_elegida"] is True


def test_varias_candidatas_sin_eleccion_requiere_seleccion():
    r = resolver([_ot("5184701", 1), _ot("5184702", 2)],
                 [_tarea(10, "5184701"), _tarea(20, "5184702")])
    assert r["ok"] is False and r["codigo"] == "SELECCION_OT_REQUERIDA"
    assert [o["numeroOt"] for o in r["ots_candidatas"]] == ["5184701", "5184702"]


@pytest.mark.parametrize("elegida", ["5184702", 5184702, " 5184702 "])
def test_varias_candidatas_con_eleccion_valida(elegida):
    r = resolver([_ot("5184701", 1), _ot(5184702, 2, titulo="Portada")],
                 [_tarea(10, "5184701"), _tarea(20, 5184702), _tarea(21, "5184702", seq=2)],
                 ot_elegida=elegida)
    assert r["ok"] and r["estado"] == "ELEGIDA"
    assert (r["wo_number"], r["tk_id"], r["titulo_ot"]) == ("5184702", 20, "Portada")
    assert r["num_candidatas"] == 3          # todas las tareas, no una por OT
    assert r["ot_elegida"] is True


@pytest.mark.parametrize("ots, tareas", [
    ([_ot("5184701", 1), _ot("5184702", 2)], [_tarea(10, "5184701"), _tarea(20, "5184702")]),
    ([_ot("5184701", 1)], [_tarea(10, "5184701")]),
    ([_ot("5184701", 1)], []),                # también sin candidatas
])
def test_eleccion_no_candidata(ots, tareas):
    r = resolver(ots, tareas, ot_elegida="5184799")
    assert r["ok"] is False and r["codigo"] == "OT_NO_CANDIDATA"
    assert len(r["ots_candidatas"]) == len(tareas)


@pytest.mark.parametrize("tareas, tk_esperada", [
    ([_tarea(30, "1", seq=3), _tarea(31, "1", seq=1)], 31),       # menor tk_seq
    ([_tarea(30, "1", seq=None), _tarea(31, "1", seq=9)], 31),    # el nulo pierde
    ([_tarea(32, "1", seq=1), _tarea(30, "1", seq=1)], 30),       # empate → menor tk_id
])
def test_tarea_repetida_en_una_ot(tareas, tk_esperada):
    r = resolver([_ot("1", 1)], tareas)
    assert r["estado"] == "AUTOMATICA" and r["tk_id"] == tk_esperada


def test_ot_o_tarea_no_abiertas_y_ot_ausente_no_cuentan():
    ots = [_ot("1", 1), _ot("2", 2, status="C"), _ot("3", 3)]
    tareas = [
        _tarea(10, "1"),
        _tarea(20, "2"),                 # OT no abierta
        _tarea(30, "3", status="C"),     # tarea no abierta
        _tarea(40, "9"),                 # OT que no está en ots
    ]
    r = resolver(ots, tareas)
    assert r["estado"] == "AUTOMATICA" and r["wo_number"] == "1"
    assert r["num_candidatas"] == 1


def test_orden_de_candidatas_op_51847():
    # Referencia: la actividad está en las OT con wo_seq 2, 4, 5, 6, 7 y 8.
    secuencias = {"5184708": 8, "5184702": 2, "5184706": 6, "5184704": 4, "5184707": 7, "5184705": 5}
    ots = [_ot(n, s) for n, s in secuencias.items()] + [_ot("5184701", 1), _ot("5184703", 3)]
    tareas = [_tarea(i, n) for i, n in enumerate(secuencias)]
    r = resolver(ots, tareas)
    assert [o["secuencia"] for o in r["ots_candidatas"]] == [2, 4, 5, 6, 7, 8]


def test_orden_con_wo_seq_nulo_al_final_y_desempate_numerico():
    ots = [_ot("100", None), _ot("20", 1), _ot("9", 1), _ot("A1", 1)]
    tareas = [_tarea(i, o["wo_number"]) for i, o in enumerate(ots)]
    r = resolver(ots, tareas)
    assert [o["numeroOt"] for o in r["ots_candidatas"]] == ["9", "20", "A1", "100"]


@pytest.mark.parametrize("titulo, esperado", [
    ("   ", None),
    (None, None),
    ("  Tripa  ", "Tripa"),
    ("x" * 61, "x" * 60),
])
def test_titulo(titulo, esperado):
    r = resolver([_ot("1", 1, titulo=titulo)], [_tarea(10, "1")])
    assert r["titulo_ot"] == esperado
    assert r["ots_candidatas"][0]["titulo"] == esperado


@pytest.mark.parametrize("ots, tareas", [
    (None, []),
    ([], "x"),
    ([{"wo_number": "1", "wo_status": "N", "wo_seq": 1}], []),          # falta wo_title2
    ([_ot("1", 1)], [{"tk_id": 1, "tk_wonum": "1", "tk_status": "N"}]),  # falta tk_seq
    ([["1"]], []),
])
def test_entrada_defectuosa(ots, tareas):
    with pytest.raises(ValueError):
        resolver(ots, tareas)

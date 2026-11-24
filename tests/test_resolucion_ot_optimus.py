"""
Lecturas de Optimus para la resolución de OT (docs/ai/14-resolucion-ot.md, iteración 2).
Doble de BD (`bd`, origen optimus1). Comportamiento nuevo (no es caracterización).
"""
import pytest

from services.ordenes_service import (
    obtener_actividades_no_cotizadas_por_recurso,
    obtener_actividades_por_recurso,
)
from services.resolucion_ot_service import resolver_desde_optimus

JOB = r"FROM job200"
WO = r"FROM wo WHERE"
TK = r"FROM wo_task200 WHERE"
STAF = r"FROM staf"
O1 = "optimus1"


def _job(status="N"):
    return [(51847, status, "N", "0", "REVISTA", 5000)]


def _evento(bd, tabla):
    """Primer evento SQL cuyo FROM principal es `tabla`."""
    for e in bd.eventos:
        if e[0] == "SQL" and e[2].split()[e[2].split().index("FROM") + 1] == tabla:
            return e
    return None


# ---------------------------------------------------------------- resolver_desde_optimus

@pytest.mark.parametrize("op", ["abc", "", "   ", "4215 0", "42150-01", "²", None])
def test_op_no_numerica_sin_consultas(bd, op):
    r = resolver_desde_optimus(op, "ACT")
    assert r["ok"] is False and r["codigo"] == "OP_INVALIDA"
    assert bd.sql() == []


def test_actividad_vacia_es_error_de_programacion(bd):
    with pytest.raises(ValueError):
        resolver_desde_optimus("51847", "  ")


def test_improductivo_no_consulta_optimus(bd):
    r = resolver_desde_optimus("12345", "MOTIVO")
    assert r["ok"] and r["estado"] == "SIN_TAREA" and r["orden"] is None
    assert bd.sql() == []


@pytest.mark.parametrize("filas, codigo", [
    ([], "OP_INEXISTENTE"),
    (_job() * 2, "RESPUESTA_INVALIDA"),
    (_job("X"), "OP_CANCELADA"),
])
def test_op_rechazada_no_consulta_wo_ni_tareas(bd, filas, codigo):
    bd.responder(JOB, filas, origen=O1)
    r = resolver_desde_optimus("51847", "ACT")
    assert r["ok"] is False and r["codigo"] == codigo and r["mensaje"]
    assert len(bd.sql()) == 1


@pytest.mark.parametrize("falla", [JOB, WO, TK])
def test_error_de_optimus_en_cada_consulta(bd, falla):
    bd.responder(falla, None, origen=O1)
    bd.responder(JOB, _job(), origen=O1)
    bd.responder(WO, [(5184701, "N", 1, None)], origen=O1)
    bd.responder(TK, [(10, 5184701, "N", 1)], origen=O1)
    r = resolver_desde_optimus("51847", "ACT")
    assert r["ok"] is False and r["codigo"] == "OPTIMUS_NO_DISPONIBLE"


def test_limite_de_ots(bd):
    bd.responder(JOB, _job(), origen=O1)
    bd.responder(WO, [(5184700 + i, "N", i, None) for i in range(101)], origen=O1)
    r = resolver_desde_optimus("51847", "ACT")
    assert r["codigo"] == "RESPUESTA_INVALIDA"
    assert _evento(bd, "wo_task200") is None


def test_limite_de_tareas(bd):
    bd.responder(JOB, _job(), origen=O1)
    bd.responder(WO, [(5184701, "N", 1, None)], origen=O1)
    bd.responder(TK, [(i, 5184701, "N", 1) for i in range(501)], origen=O1)
    assert resolver_desde_optimus("51847", "ACT")["codigo"] == "RESPUESTA_INVALIDA"


def test_op_sin_ots_no_consulta_tareas(bd):
    bd.responder(JOB, _job(), origen=O1)
    r = resolver_desde_optimus("51847", "ACT")
    assert r["ok"] and r["estado"] == "SIN_TAREA"
    assert r["orden"] == {"num_op": "51847", "descripcion": "REVISTA", "cantidad": 5000}
    assert _evento(bd, "wo_task200") is None


def test_varias_ots_con_eleccion_y_sql_parametrizado(bd):
    bd.responder(JOB, _job(), origen=O1)
    bd.responder(WO, [(5184702, "N", 2, "Tripa"), (5184704, "N", 4, "Portada"), (5184703, "C", 3, None)],
                 origen=O1)
    bd.responder(TK, [(20, 5184702, "N", 1), (40, 5184704, "N", 2), (41, 5184704, "N", 1)], origen=O1)

    r = resolver_desde_optimus("51847", "H TIR FG", ot_elegida="5184704")

    assert r["ok"] and r["estado"] == "ELEGIDA"
    assert (r["wo_number"], r["tk_id"], r["titulo_ot"]) == ("5184704", 41, "Portada")
    assert r["orden"]["num_op"] == "51847"

    _, _, sql_job, params_job = _evento(bd, "job200")
    _, _, sql_wo, params_wo = _evento(bd, "wo")
    _, _, sql_tk, params_tk = _evento(bd, "wo_task200")
    assert params_job == ("51847",) and params_wo == ("51847",)
    assert "51847" not in sql_job + sql_wo
    assert "wo200" not in sql_job + sql_wo + sql_tk
    assert "IN (%s, %s, %s) AND tk_code = %s" in sql_tk          # un %s por OT leída
    assert params_tk == (5184702, 5184704, 5184703, "H TIR FG")
    assert "H TIR FG" not in sql_tk


def test_eleccion_en_blanco_cuenta_como_sin_eleccion(bd):
    bd.responder(JOB, _job(), origen=O1)
    bd.responder(WO, [(5184702, "N", 2, None), (5184704, "N", 4, None)], origen=O1)
    bd.responder(TK, [(20, 5184702, "N", 1), (40, 5184704, "N", 1)], origen=O1)
    assert resolver_desde_optimus("51847", "ACT", ot_elegida="  ")["codigo"] == "SELECCION_OT_REQUERIDA"


# ---------------------------------------------------------------- actividades

@pytest.mark.parametrize("funcion, existe", [
    (obtener_actividades_por_recurso, "AND EXISTS"),
    (obtener_actividades_no_cotizadas_por_recurso, "AND NOT EXISTS"),
])
def test_actividades_por_op_vigentes(bd, funcion, existe):
    bd.responder(r"FROM act", [("H TIR FG", "TIRAJE")], origen=O1)
    actividades = funcion("51847", "PEG CAJ2")

    assert actividades[0]["codigo"] == "H TIR FG"
    (_, _, sql, params), = [e for e in bd.eventos if e[0] == "SQL"]
    assert "wo.wo_job = %s" in sql and "act.act_discont = '0'" in sql and existe in sql
    assert "wo200" not in sql and "01" not in sql
    assert params == ("PEG CAJ2", "51847")


def test_actividades_op_no_numerica(bd):
    with pytest.raises(ValueError):
        obtener_actividades_por_recurso("51847A", "PEG CAJ2")
    assert bd.sql() == []


def test_actividades_api_exige_num_op(cliente):
    r = cliente.post("/api/actividades/recurso", json={"num_ot": "5184701", "recurso": "PEG CAJ2"})
    assert r.status_code == 422


# ---------------------------------------------------------------- POST /api/op/ots

def _ots(cliente, op="51847", actividad="ACT"):
    return cliente.post("/api/op/ots", json={"num_op": op, "actividad": actividad})


def test_ots_requiere_eleccion_con_lista_ordenada(cliente, bd):
    bd.responder(JOB, _job(), origen=O1)
    bd.responder(WO, [(5184708, "N", 8, None), (5184702, "N", 2, "Tripa")], origen=O1)
    bd.responder(TK, [(80, 5184708, "N", 1), (20, 5184702, "N", 1)], origen=O1)
    r = _ots(cliente)
    assert r.status_code == 200
    assert r.json()["requiereEleccion"] is True
    assert [o["numeroOt"] for o in r.json()["ots"]] == ["5184702", "5184708"]
    assert r.json()["ots"][0] == {"numeroOt": "5184702", "titulo": "Tripa", "secuencia": 2}


def test_ots_sin_eleccion(cliente, bd):
    bd.responder(JOB, _job(), origen=O1)
    bd.responder(WO, [(5184702, "N", 2, None)], origen=O1)
    bd.responder(TK, [(20, 5184702, "N", 1)], origen=O1)
    r = _ots(cliente)
    assert r.status_code == 200 and r.json() == {"ok": True, "requiereEleccion": False, "ots": []}


@pytest.mark.parametrize("filas, estado, codigo", [
    (_job("X"), 409, "OP_CANCELADA"),
    ([], 409, "OP_INEXISTENTE"),
    (None, 503, "OPTIMUS_NO_DISPONIBLE"),
])
def test_ots_rechazos(cliente, bd, filas, estado, codigo):
    bd.responder(JOB, filas, origen=O1)
    r = _ots(cliente)
    assert r.status_code == estado
    assert r.json()["detail"]["codigo"] == codigo and r.json()["detail"]["mensaje"]


@pytest.mark.parametrize("cuerpo", [{"num_op": "51847-01", "actividad": "ACT"}, {"num_op": "51847", "actividad": " "}])
def test_ots_valida_el_cuerpo(cliente, cuerpo):
    assert cliente.post("/api/op/ots", json=cuerpo).status_code == 422


# ---------------------------------------------------------------- POST /api/op/buscar

@pytest.mark.parametrize("filas, texto", [
    ([], "no existe"),
    (_job("X"), "cancelada"),
])
def test_buscar_op_rechazada_400(cliente, bd, filas, texto):
    bd.responder(STAF, [("M1", "OPERARIO UNO", "PEG CAJ2")], origen=O1)
    bd.responder(JOB, filas, origen=O1)
    r = cliente.post("/api/op/buscar", json={"num_op": "51847", "codigo_usuario": "M1"})
    assert r.status_code == 400
    assert texto in r.json()["detail"]


def test_buscar_op_lee_job200_sin_suponer_ot_01(cliente, bd):
    bd.responder(STAF, [("M1", "OPERARIO UNO", "PEG CAJ2")], origen=O1)
    bd.responder(JOB, _job(), origen=O1)
    r = cliente.post("/api/op/buscar", json={"num_op": "51847", "codigo_usuario": "M1"})
    assert r.status_code == 200
    # Iteración 5 (2026-11-24): la respuesta ya no incluye el antiguo campo OT = OP + "01".
    assert r.json()["orden"] == {"num_op": "51847", "descripcion": "REVISTA", "cantidad": 5000}
    # Ya no se busca la OT "OP+01" en wo200. (La lista de recursos, fuera de alcance por R-10, sigue leyendo wo200.)
    assert not any("wo_number = %s" in s for s in bd.sql())

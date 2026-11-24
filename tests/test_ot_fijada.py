"""
OT y tarea fijadas al abrir, heredadas por el relevo MT y copiadas por el cierre
(docs/ai/14-resolucion-ot.md, iteración 4). Comportamiento nuevo (no es caracterización).
"""
import pytest

from services.cierres_service import ejecutar_cierre_marcaje_real
from tests.test_cierre_marcaje import MARCAJE, preparar

MAC = "AABBCCDDEEFF"
URL = "/api/marcajes/iniciar-real-bd"
PAYLOAD = {
    "num_op": "51151", "descripcion": "CAJA", "cantidad": "1000", "recurso": "PEG CAJ2",
    "actividad": "H TIR FG", "actividad_nombre": "TIRAJE", "codigo_usuario": "M1",
}
O1 = "optimus1"
OT_FIJADA = r"SELECT wo_number, tk_id, estadoResolucion"


@pytest.fixture
def maquina_libre(bd, escritura_habilitada):
    bd.responder(r"FROM smartfactory.macdirectorio", [(MAC,)])
    return bd


def _op_con_dos_ots(bd, titulo2="Tripa d'oro"):
    bd.responder(r"FROM job200", [(51151, "N", "N", "0", "CAJA", 1000)], origen=O1)
    bd.responder(r"FROM wo WHERE", [(5115101, "N", 1, "Portada"), (5115102, "N", 2, titulo2)], origen=O1)
    bd.responder(r"FROM wo_task200 WHERE", [(11, 5115101, "N", 1), (21, 5115102, "N", 1)], origen=O1)


def _insert_marcajeactivo(bd):
    return [s for s in bd.escrituras() if s.startswith("INSERT INTO smartfactory.marcajeactivo")][0]


# ---------------------------------------------------------------- apertura

@pytest.mark.parametrize("numero_ot, codigo", [(None, "SELECCION_OT_REQUERIDA"), (9999999, "OT_NO_CANDIDATA")])
def test_rechazo_de_resolucion_sin_efectos(cliente, maquina_libre, numero_ot, codigo):
    _op_con_dos_ots(maquina_libre)
    r = cliente.post(URL, json={**PAYLOAD, "numero_ot": numero_ot})
    assert r.status_code == 409
    detalle = r.json()["detail"]
    assert detalle["modo"] == "RESOLUCION_OT" and detalle["codigo"] == codigo and detalle["mensaje"]
    assert [o["numeroOt"] for o in detalle["ots_candidatas"]] == ["5115101", "5115102"]
    assert maquina_libre.secuencia() == []
    assert maquina_libre.sql("smartfactory") == []   # ni macdirectorio ni marcajeactivo


def test_optimus_no_disponible_503_sin_efectos(cliente, maquina_libre):
    maquina_libre.responder(r"FROM job200", None, origen=O1)
    r = cliente.post(URL, json=PAYLOAD)
    assert r.status_code == 503
    assert r.json()["detail"]["codigo"] == "OPTIMUS_NO_DISPONIBLE"
    assert maquina_libre.secuencia() == [] and maquina_libre.sql("smartfactory") == []


def test_elegida_escribe_ot_tarea_y_titulo_escapado(cliente, maquina_libre):
    _op_con_dos_ots(maquina_libre)
    r = cliente.post(URL, json={**PAYLOAD, "numero_ot": 5115102, "num_ot": "5115101"})  # num_ot se ignora
    assert r.status_code == 200, r.text
    assert maquina_libre.secuencia() == ["INSERT INTO smartfactory.marcajeactivo", f"MQTT {MAC}-OP"]
    insert = _insert_marcajeactivo(maquina_libre)
    assert "wo_number, tk_id, estadoResolucion, tituloOt)" in insert
    assert insert.endswith("5115102, 21, 'ELEGIDA', 'Tripa d''oro');")
    assert r.json()["resolucion"]["estadoResolucion"] == "ELEGIDA"


def test_sin_tarea_escribe_null(cliente, maquina_libre):
    maquina_libre.responder(r"FROM job200", [(51151, "N", "N", "0", "CAJA", 1000)], origen=O1)
    maquina_libre.responder(r"FROM wo WHERE", [(5115101, "N", 1, "Portada")], origen=O1)
    r = cliente.post(URL, json=PAYLOAD)          # la actividad no tiene tarea en ninguna OT
    assert r.status_code == 200, r.text
    assert _insert_marcajeactivo(maquina_libre).endswith("NULL, NULL, 'SIN_TAREA', NULL);")
    assert maquina_libre.secuencia() == ["INSERT INTO smartfactory.marcajeactivo", f"MQTT {MAC}-OP"]


def test_improductivo_sin_tarea_sin_consultar_optimus(cliente, maquina_libre):
    r = cliente.post("/api/marcajes/iniciar-improductivo", json={
        **PAYLOAD, "num_op": "12345", "cantidad": "12345", "actividad": "COMIDA"})
    assert r.status_code == 200, r.text
    assert _insert_marcajeactivo(maquina_libre).endswith("NULL, NULL, 'SIN_TAREA', NULL);")
    assert maquina_libre.sql(O1) == []


# ---------------------------------------------------------------- relevo MT

def _relevo(cliente, **ot):
    relevo = {"numOp": "51151", "descrip": "CAJA", "cantidadcot": "1000", "recurso": "PEG CAJ2",
              "actividad": "H TIR FG", "actividad_nombre": "TIRAJE", **ot}
    return cliente.post("/api/marcajes/iniciar-relevo-mt-real", json={"relevo": relevo, "codigo_usuario": "M2"})


@pytest.mark.parametrize("ot, final_insert", [
    ({"wo_number": 5115102, "tk_id": 21, "estadoResolucion": "ELEGIDA", "tituloOt": "Tripa"},
     "5115102, 21, 'ELEGIDA', 'Tripa');"),
    ({"wo_number": 0, "tk_id": 0, "estadoResolucion": "SIN_TAREA", "tituloOt": None},
     "NULL, NULL, 'SIN_TAREA', NULL);"),
    ({"wo_number": 5115101, "tk_id": 7, "estadoResolucion": None, "tituloOt": None},   # marcaje antiguo
     "NULL, NULL, NULL, NULL);"),
    ({}, "NULL, NULL, NULL, NULL);"),
])
def test_relevo_hereda_sin_consultar_optimus(cliente, maquina_libre, ot, final_insert):
    r = _relevo(cliente, **ot)
    assert r.status_code == 200, r.text
    assert _insert_marcajeactivo(maquina_libre).endswith(final_insert)
    assert maquina_libre.sql(O1) == []


@pytest.mark.parametrize("ot", [
    {"wo_number": 5115102, "tk_id": None, "estadoResolucion": "AUTOMATICA"},
    {"wo_number": "abc", "tk_id": 21, "estadoResolucion": "ELEGIDA"},
    {"wo_number": 5115102, "tk_id": 21, "estadoResolucion": "SIN_TAREA"},
    {"wo_number": None, "tk_id": None, "estadoResolucion": "OTRO"},
])
def test_relevo_incoherente_sin_efectos(cliente, maquina_libre, ot):
    r = _relevo(cliente, **ot)
    assert r.status_code == 409
    assert r.json()["detail"]["modo"] == "DATOS_RELEVO_INCOMPLETOS"
    assert maquina_libre.secuencia() == [] and maquina_libre.sql() == []


# ---------------------------------------------------------------- cierre

def _resumenes(bd):
    return [s for s in bd.escrituras() if s.startswith("INSERT INTO smartfactory.resumenmarcajes")]


@pytest.mark.parametrize("fila, esperado", [
    ((5115102, 21, "ELEGIDA", "Tripa"), "'5115102', '21'"),
    ((None, None, "SIN_TAREA", None), "'0', '0'"),
])
def test_cierre_copia_la_ot_fijada_sin_optimus(bd, escritura_habilitada, fila, esperado):
    bd.responder(OT_FIJADA, [fila])            # antes que la fila antigua de preparar()
    preparar(bd)
    r = ejecutar_cierre_marcaje_real(MARCAJE, "FINAL", 0)
    assert r["ok"] is True, r
    usuario, fila_f = _resumenes(bd)
    assert esperado in usuario and esperado in fila_f
    assert bd.sql("optimus") == []             # no recalcula con wo_task200
    assert r["valores"]["estadoResolucion"] == fila[2]


def test_cierre_sin_estado_usa_respaldo(bd, escritura_habilitada):
    preparar(bd)                               # fila con estadoResolucion NULL
    r = ejecutar_cierre_marcaje_real(MARCAJE, "FINAL", 0)
    assert r["ok"] is True
    assert any("wo_task200" in s for s in bd.sql("optimus"))
    assert all("'5115101', '7'" in s for s in _resumenes(bd))


def test_cierre_error_bd_al_leer_ot_sin_efectos(bd, mqtt, escritura_habilitada):
    bd.responder(OT_FIJADA, None)
    preparar(bd)
    r = ejecutar_cierre_marcaje_real(MARCAJE, "FINAL", 0)
    assert r["ok"] is False and r["modo"] == "ERROR_BD_OT"
    assert bd.secuencia() == [] and mqtt.publicaciones == []


def test_mt_relevo_pendiente_lleva_la_ot(bd, escritura_habilitada):
    bd.responder(OT_FIJADA, [(5115102, 21, "ELEGIDA", "Tripa")])
    preparar(bd)
    relevo = ejecutar_cierre_marcaje_real(MARCAJE, "MT", 0)["relevo_pendiente"]
    assert "num_ot" not in relevo
    assert {k: relevo[k] for k in ("wo_number", "tk_id", "estadoResolucion", "tituloOt")} == {
        "wo_number": 5115102, "tk_id": 21, "estadoResolucion": "ELEGIDA", "tituloOt": "Tripa"}

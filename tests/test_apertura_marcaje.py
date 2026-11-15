"""Apertura de marcajes: validaciones, orden INSERT → MQTT, efecto de los flags (docs/ai/04 §0, §2-3)."""
import pytest

MAC = "AABBCCDDEEFF"
PAYLOAD = {
    "num_op": "51151", "num_ot": "5115101", "descripcion": "CAJA", "cantidad": "1000",
    "recurso": "PEG CAJ2", "actividad": "H TIR FG", "actividad_nombre": "TIRAJE", "codigo_usuario": "M1",
}
IMPRODUCTIVO = {
    "num_op": "12345", "descripcion": "Tiempo Improductivo", "cantidad": "12345",
    "recurso": "PEG CAJ2", "actividad": "COMIDA", "actividad_nombre": "Tiempo de Comida", "codigo_usuario": "M1",
}
URL = "/api/marcajes/iniciar-real-bd"


@pytest.fixture
def maquina_libre(bd):
    bd.responder(r"FROM smartfactory.macdirectorio", [(MAC,)])
    return bd


def test_flags_desactivados_no_escriben_ni_publican(cliente, maquina_libre, mqtt):
    r = cliente.post(URL, json=PAYLOAD)
    assert r.status_code == 409
    assert r.json()["detail"]["modo"] == "PROTEGIDO"
    assert maquina_libre.escrituras() == []
    assert mqtt.publicaciones == []


def test_apertura_inserta_y_despues_publica(cliente, maquina_libre, escritura_habilitada):
    r = cliente.post(URL, json=PAYLOAD)
    assert r.status_code == 200, r.text
    assert maquina_libre.secuencia() == ["INSERT INTO smartfactory.marcajeactivo", f"MQTT {MAC}-OP"]
    mqtt_evento = [e for e in maquina_libre.eventos if e[0] == "MQTT"][0]
    assert mqtt_evento[2] == "51151,PEG CAJ2,H TIR FG,1000,100,2024/10/09,08:31:55,2024/10/09,18:30:55,0,1"
    ids = [m["id"] for m in r.json()["marcajes"]]
    assert ids == ["REAL_BD|M1|51151|PEG CAJ2|H TIR FG"]


@pytest.mark.caracterizacion
def test_publicacion_fallida_deja_el_marcaje_abierto(cliente, maquina_libre, escritura_habilitada, mqtt):
    """R-04/§0: el INSERT ya ocurrió; la respuesta sigue siendo ok."""
    mqtt.resultado = {"ok": False, "mensaje": "broker caído (doble)"}
    r = cliente.post(URL, json=PAYLOAD)
    assert r.status_code == 200
    assert "NO fue publicado" in r.json()["mensaje"]
    assert maquina_libre.escrituras()[0].startswith("INSERT INTO smartfactory.marcajeactivo")


def test_maquina_ocupada_bloquea(cliente, maquina_libre, escritura_habilitada):
    maquina_libre.responder(r"FROM smartfactory.marcajeactivo WHERE recurso",
                            [(1, "PEG CAJ2", "X", "M9", f"{MAC}-OP")])
    r = cliente.post(URL, json=PAYLOAD)
    assert r.status_code == 409
    assert r.json()["detail"]["bloqueo"] == "RECURSO_O_TOPIC_BD"
    assert maquina_libre.escrituras() == []


def test_recurso_sin_mac_bloquea(cliente, bd, escritura_habilitada):
    r = cliente.post(URL, json=PAYLOAD)
    assert r.status_code == 409
    assert "MAC" in r.json()["detail"]["mensaje"]


@pytest.mark.caracterizacion
def test_error_de_bd_en_validaciones_no_bloquea(cliente, maquina_libre, escritura_habilitada):
    """R-03: None (error) en las validaciones de marcajeactivo se interpreta como 'libre'."""
    maquina_libre.responder(r"FROM smartfactory.marcajeactivo", None)
    r = cliente.post(URL, json=PAYLOAD)
    assert r.status_code == 200
    assert maquina_libre.escrituras()[0].startswith("INSERT INTO smartfactory.marcajeactivo")


@pytest.mark.caracterizacion
def test_improductivo_publica_inicio_con_op_12345(cliente, maquina_libre, escritura_habilitada, mqtt):
    r = cliente.post("/api/marcajes/iniciar-improductivo", json=IMPRODUCTIVO)
    assert r.status_code == 200, r.text
    assert mqtt.publicaciones[0][1].startswith("12345,PEG CAJ2,COMIDA,12345,")
    # R-18: en memoria el improductivo queda sin cantidad
    assert r.json()["marcaje"]["cantidad"] is None

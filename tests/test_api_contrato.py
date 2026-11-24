"""Contrato HTTP que consume static/js/app.js (códigos y forma de las respuestas)."""
import pytest

STAF = r"FROM staf"


def test_health(cliente):
    r = cliente.get("/api/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_identificar_valida_el_cuerpo(cliente):
    assert cliente.post("/api/usuario/identificar-prueba", json={}).status_code == 422


def test_identificar_usuario_inexistente_404(cliente, bd):
    r = cliente.post("/api/usuario/identificar-prueba", json={"codigo_usuario": "X1"})
    assert r.status_code == 404
    assert "no encontrado" in r.json()["detail"].lower()


@pytest.mark.caracterizacion
def test_identificar_error_optimus_se_reporta_como_inexistente(cliente, bd):
    """R-03: un error de BD (None) se muestra como 'usuario no encontrado'."""
    bd.responder(STAF, None, origen="optimus1")
    assert cliente.post("/api/usuario/identificar-prueba", json={"codigo_usuario": "M1"}).status_code == 404


def test_identificar_sin_marcaje_pasa_a_ingresar_op(cliente, bd):
    bd.responder(STAF, [("M1", "OPERARIO UNO", "PEG CAJ2")], origen="optimus1")
    r = cliente.post("/api/usuario/identificar-prueba", json={"codigo_usuario": "M1"})
    assert r.status_code == 200
    datos = r.json()
    assert datos["usuario"] == {"code": "M1", "username": "OPERARIO UNO", "resource": "PEG CAJ2"}
    assert datos["marcaje_activo"] is None
    assert datos["siguiente_paso"] == "ingresar_op"


def test_identificar_con_marcaje_activo_pasa_a_cerrar(cliente, bd):
    bd.responder(STAF, [("M1", "OPERARIO UNO", "PEG CAJ2")], origen="optimus1")
    bd.responder(r"FROM smartfactory.marcajeactivo WHERE username",
                 [(51151, "DESC", 1000, "PEG CAJ2", "H TIR FG", "M1", "AABBCCDDEEFF-OP", "UNIDAD")])
    datos = cliente.post("/api/usuario/identificar-prueba", json={"codigo_usuario": "M1"}).json()
    assert datos["siguiente_paso"] == "cerrar_marcaje"
    assert datos["marcaje_activo"]["id"] == "REAL_BD|M1|51151|PEG CAJ2|H TIR FG"
    assert datos["marcaje_activo"]["mac"] == "AABBCCDDEEFF"


def test_buscar_op_no_numerica_400(cliente):
    r = cliente.post("/api/op/buscar", json={"num_op": "abc", "codigo_usuario": "M1"})
    assert r.status_code == 400


@pytest.mark.parametrize("op", ["123", "2000000"])
def test_buscar_op_sin_rango_p20(cliente, bd, op):
    """P-20 (decisión del 2026-11-24): se elimina el rango 10 000-1 000 000; basta con
    que la OP sea numérica, exista en job200 y sea elegible."""
    bd.responder(STAF, [("M1", "OPERARIO UNO", "PEG CAJ2")], origen="optimus1")
    bd.responder(r"FROM job200", [(int(op), "N", "N", "0", "CAJA", 1000)], origen="optimus1")
    r = cliente.post("/api/op/buscar", json={"num_op": op, "codigo_usuario": "M1"})
    assert r.status_code == 200
    assert r.json()["orden"]["num_op"] == op


def test_cierre_tipo_invalido_409_con_detalle_dict(cliente):
    """app.js lee detail.mensaje cuando detail es un objeto."""
    r = cliente.post("/api/marcajes/ejecutar-cierre-real",
                     json={"marcaje": {"numOp": "1"}, "tipo_cierre": "XX", "total_usuario": 0})
    assert r.status_code == 409
    assert "Tipo de cierre inválido" in r.json()["detail"]["mensaje"]

"""Garantías de aislamiento. Si alguna falla, NINGUNA otra prueba es fiable."""
import importlib.util
import socket

import pytest


def test_db_conexion_es_el_doble():
    import db.conexion

    assert getattr(db.conexion, "ES_DOBLE_DE_PRUEBAS", False) is True


@pytest.mark.parametrize("paquete", ["mysql", "pyodbc", "paho"])
def test_drivers_reales_no_disponibles(paquete):
    # .venv-test no los instala a propósito (requirements-dev.txt).
    assert importlib.util.find_spec(paquete) is None


def test_flags_de_escritura_desactivados():
    import config

    assert config.ENABLE_REAL_DB_WRITES is False
    assert config.ENABLE_REAL_MQTT_DB_WRITES is False
    assert config.ENABLE_REAL_MQTT_PUBLISH is False


def test_red_externa_bloqueada():
    with pytest.raises(RuntimeError, match="bloqueada"):
        socket.create_connection(("192.0.2.1", 3306), timeout=0.1)  # TEST-NET-1, nunca enrutable


def test_logs_reales_no_se_usan(tmp_path):
    import services.cierres_service as cierres
    import services.persistencia_marcajes_service as persistencia

    assert str(persistencia.LOG_FILE).startswith(str(tmp_path))
    assert str(cierres.LOG_CANTIDADREAL_NEGATIVA_FILE).startswith(str(tmp_path))

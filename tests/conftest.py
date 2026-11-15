"""
Infraestructura de pruebas aisladas de SmartFactory Web.

ESTE ARCHIVO SE CARGA ANTES QUE CUALQUIER MÓDULO DEL PROYECTO y aplica cinco barreras:

1. Flags SMARTFACTORY_ENABLE_REAL_* = "0" antes de importar `config`
   (config.py usa os.environ.setdefault, así que respeta estos valores).
2. Red bloqueada salvo loopback. asyncio y TestClient en Windows usan socketpair en 127.0.0.1.
3. `db.conexion` sustituido por un doble (`BD`) que registra cada SQL y responde
   según reglas programadas. El driver real ni siquiera está instalado en .venv-test.
4. `mqtt_monitor.publicar`, `.iniciar` y `.detener` sustituidos (fixture `mqtt`).
   paho-mqtt tampoco está instalado en .venv-test.
5. Los logs de los servicios se redirigen a tmp_path para no tocar `logs/` reales.

Cómo usar el doble de BD:
    bd.responder(r"FROM smartfactory.macdirectorio", [("AABBCCDDEEFF",)])
    bd.responder(r"INSERT INTO smartfactory.resumenmarcajes", None)   # simula un error de BD
    bd.eventos   -> lista ordenada de ("SQL", origen, sql_normalizado, params) y ("MQTT", topic, payload)

Reglas: gana la PRIMERA que coincide (regex, sin distinguir mayúsculas). Sin regla:
SELECT → [] y escritura en smartfactory → "Operación exitosa" (igual que dtbSmartFactory).
"""
from __future__ import annotations

import os
import re
import socket
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.dont_write_bytecode = True  # las pruebas no escriben .pyc en el árbol de código

# ---------------------------------------------------------------- 1. flags
for _flag in (
    "SMARTFACTORY_ENABLE_REAL_DB_WRITES",
    "SMARTFACTORY_ENABLE_REAL_MQTT_DB_WRITES",
    "SMARTFACTORY_ENABLE_REAL_MQTT_PUBLISH",
):
    os.environ[_flag] = "0"
os.environ["SMARTFACTORY_MQTT_BROKER"] = "127.0.0.1"  # defensa adicional

# ---------------------------------------------------------------- 2. red
_LOOPBACK = {"127.0.0.1", "localhost", "::1"}
_connect_real = socket.socket.connect
_connect_ex_real = socket.socket.connect_ex
_create_connection_real = socket.create_connection


def _host(direccion):
    return direccion[0] if isinstance(direccion, tuple) and direccion else direccion


def _verificar(direccion):
    if _host(direccion) not in _LOOPBACK:
        raise RuntimeError(f"PRUEBAS: conexión de red bloqueada hacia {direccion!r}")


def _connect_guardado(self, direccion):
    _verificar(direccion)
    return _connect_real(self, direccion)


def _connect_ex_guardado(self, direccion):
    _verificar(direccion)
    return _connect_ex_real(self, direccion)


def _create_connection_guardado(direccion, *args, **kwargs):
    _verificar(direccion)
    return _create_connection_real(direccion, *args, **kwargs)


socket.socket.connect = _connect_guardado
socket.socket.connect_ex = _connect_ex_guardado
socket.create_connection = _create_connection_guardado


# ---------------------------------------------------------------- 3. doble de BD
class BDFalsa:
    def __init__(self) -> None:
        self.reiniciar()

    def reiniciar(self) -> None:
        self.eventos: list[tuple] = []
        self._reglas: list[tuple[re.Pattern, object, str | None]] = []

    def responder(self, patron: str, respuesta, origen: str | None = None) -> None:
        """respuesta: lista de filas, None (error de BD), una excepción o un callable(sql, params)."""
        self._reglas.append((re.compile(patron, re.I | re.S), respuesta, origen))

    def ejecutar(self, origen: str, sql: str, params=None):
        normalizado = " ".join(str(sql).split())
        self.eventos.append(("SQL", origen, normalizado, params))
        for patron, respuesta, origen_regla in self._reglas:
            if (origen_regla is None or origen_regla == origen) and patron.search(normalizado):
                if isinstance(respuesta, BaseException):
                    raise respuesta
                if callable(respuesta):
                    return respuesta(normalizado, params)
                return respuesta
        es_escritura = normalizado.lower().startswith(("insert", "update", "delete"))
        if origen == "smartfactory" and es_escritura:
            return "Operación exitosa"
        return []

    # --- consultas de ayuda para las aserciones
    def sql(self, origen: str | None = None) -> list[str]:
        return [e[2] for e in self.eventos if e[0] == "SQL" and (origen is None or e[1] == origen)]

    def escrituras(self) -> list[str]:
        return [s for s in self.sql("smartfactory") if s.lower().startswith(("insert", "update", "delete"))]

    def secuencia(self) -> list[str]:
        """Eventos con efecto (escrituras SQL y publicaciones MQTT) en orden, abreviados."""
        salida = []
        for e in self.eventos:
            if e[0] == "MQTT":
                salida.append(f"MQTT {e[1]}")
            elif e[1] == "smartfactory" and e[2].lower().startswith(("insert", "update", "delete")):
                salida.append(" ".join(e[2].split()[:3]))
        return salida


BD = BDFalsa()

_falso = types.ModuleType("db.conexion")
_falso.__doc__ = "Doble de pruebas de db/conexion.py (sin drivers ni red)."


class dtbSmartFactory:
    def __init__(self, query):
        self.query = query

    def consultaSmartFactory(self):
        return BD.ejecutar("smartfactory", self.query)


class dtbOptimus:
    def __init__(self, query):
        self.query = query

    def consultaOptimus(self):
        return BD.ejecutar("optimus", self.query)


class dtbOptimus1:
    def __init__(self, query, params=None):
        self.query = query
        self.params = params

    def consultaOptimus(self):
        return BD.ejecutar("optimus1", self.query, self.params)


class dtbEntregasDiarias:
    def __init__(self, query):
        self.query = query

    def consultaEntregasDiarias(self):
        return BD.ejecutar("entregas", self.query)


for _clase in (dtbSmartFactory, dtbOptimus, dtbOptimus1, dtbEntregasDiarias):
    setattr(_falso, _clase.__name__, _clase)
_falso.ES_DOBLE_DE_PRUEBAS = True

sys.path.insert(0, str(ROOT))
import db  # noqa: E402  (paquete real: __init__.py vacío)

sys.modules["db.conexion"] = _falso
db.conexion = _falso


# ---------------------------------------------------------------- fixtures
@pytest.fixture(autouse=True)
def bd(monkeypatch, tmp_path):
    """Doble de BD limpio y logs redirigidos a tmp_path en cada prueba."""
    BD.reiniciar()

    import services.cierres_service as cierres
    import services.mqtt_persistencia_simulada_service as mqtt_pers
    import services.persistencia_marcajes_service as persistencia
    from services import marcajes_estado_service

    monkeypatch.setattr(persistencia, "LOG_FILE", tmp_path / "marcajes_reales.log")
    monkeypatch.setattr(cierres, "LOG_CANTIDADREAL_NEGATIVA_FILE", tmp_path / "cantidadreal_negativos.log")
    monkeypatch.setattr(mqtt_pers, "LOG_FILE", tmp_path / "mqtt_persistencia.log")
    monkeypatch.setattr(mqtt_pers, "LOG_ALERTA_CONGLOMERADO_FILE", tmp_path / "mqtt_alertas.log")

    marcajes_estado_service.reemplazar_estado_marcajes([])
    yield BD
    marcajes_estado_service.reemplazar_estado_marcajes([])


class MqttFalso:
    """Registra publicaciones en BD.eventos para poder verificar el orden SQL ↔ MQTT."""

    def __init__(self) -> None:
        self.resultado = {"ok": True, "mensaje": "Mensaje MQTT publicado correctamente (doble)."}
        self.publicaciones: list[tuple[str, str]] = []

    def publicar(self, topic, payload):
        topic, payload = str(topic or "").strip(), str(payload or "").strip()
        self.publicaciones.append((topic, payload))
        BD.eventos.append(("MQTT", topic, payload))
        return {**self.resultado, "topic": topic, "payload": payload}


@pytest.fixture(autouse=True)
def mqtt(monkeypatch):
    """Sustituye la publicación, el arranque y la parada de MQTT en todas las pruebas."""
    from services.mqtt_service import mqtt_monitor

    falso = MqttFalso()

    async def _sin_conexion(*_a, **_k):
        return {"ok": True, "mensaje": "MQTT deshabilitado en pruebas", "estado": {}}

    monkeypatch.setattr(mqtt_monitor, "publicar", falso.publicar)
    monkeypatch.setattr(mqtt_monitor, "iniciar", _sin_conexion)
    monkeypatch.setattr(mqtt_monitor, "detener", _sin_conexion)
    return falso


@pytest.fixture
def escritura_habilitada(monkeypatch):
    """Activa los flags de escritura SOLO en los módulos (con BD y MQTT falsos)."""
    import services.cierres_service as cierres
    import services.persistencia_marcajes_service as persistencia

    for modulo in (persistencia, cierres):
        monkeypatch.setattr(modulo, "ENABLE_REAL_DB_WRITES", True)
        monkeypatch.setattr(modulo, "ENABLE_REAL_MQTT_PUBLISH", True)


@pytest.fixture
def cliente():
    """TestClient sin context manager: NO ejecuta los eventos startup/shutdown."""
    from fastapi.testclient import TestClient

    from main import app

    return TestClient(app)

from collections import deque
from datetime import datetime
from typing import Any

_MAX_MENSAJES = 80
_MENSAJES_MQTT: deque[dict[str, Any]] = deque(maxlen=_MAX_MENSAJES)

_ESTADO_MQTT: dict[str, Any] = {
    "conectado": False,
    "ejecutando": False,
    "broker": None,
    "puerto": None,
    "ultimo_evento": None,
    "ultimo_error": None,
    "suscripciones": [],
    "cantidad_mensajes": 0,
}


def ahora_texto() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def actualizar_estado_mqtt(**kwargs: Any) -> dict[str, Any]:
    _ESTADO_MQTT.update(kwargs)
    _ESTADO_MQTT["ultimo_evento"] = ahora_texto()
    return obtener_estado_mqtt()


def registrar_mensaje_mqtt(topic: str, payload: str, mac: str | None = None, tipo: str | None = None) -> dict[str, Any]:
    mensaje = {
        "fecha_hora": ahora_texto(),
        "topic": topic,
        "payload": payload,
        "mac": mac,
        "tipo": tipo,
    }

    _MENSAJES_MQTT.appendleft(mensaje)
    _ESTADO_MQTT["cantidad_mensajes"] = _ESTADO_MQTT.get("cantidad_mensajes", 0) + 1
    _ESTADO_MQTT["ultimo_evento"] = ahora_texto()

    return mensaje


def listar_mensajes_mqtt() -> list[dict[str, Any]]:
    return list(_MENSAJES_MQTT)


def obtener_estado_mqtt() -> dict[str, Any]:
    estado = dict(_ESTADO_MQTT)
    estado["ultimos_mensajes"] = listar_mensajes_mqtt()[:20]
    return estado

from datetime import datetime
from typing import Any
from uuid import uuid4
import re

# Estado temporal en memoria.
# IMPORTANTE: Esta fase es de simulación. Al reiniciar uvicorn se limpia.
_MARCAJES_ACTIVOS_SIMULADOS: list[dict[str, Any]] = []


def listar_marcajes_activos_simulados() -> list[dict[str, Any]]:
    return list(_MARCAJES_ACTIVOS_SIMULADOS)


def _extraer_mac_desde_topic(topic: str | None) -> str | None:
    if not topic or "-" not in topic:
        return None
    return str(topic).split("-", 1)[0].strip()


def _extraer_tipo_desde_topic(topic: str | None) -> str | None:
    if not topic or "-" not in topic:
        return None
    return str(topic).split("-", 1)[1].strip()


def _parsear_payload_datos(payload: str | None) -> dict[str, Any]:
    """
    Interpreta de manera segura el payload recibido por MQTT.

    En versiones anteriores del sistema se han visto mensajes con este formato:
        numOp,cantidad,actividad

    Ejemplo:
        47874,51911,D-TIR-F2

    Esta función NO falla si el formato cambia; solamente devuelve lo que pueda detectar.
    """
    texto = "" if payload is None else str(payload).strip()
    partes = [p.strip() for p in texto.split(",")] if texto else []

    num_op = partes[0] if len(partes) >= 1 and partes[0] else None
    cantidad_raw = partes[1] if len(partes) >= 2 and partes[1] else None
    actividad = partes[2] if len(partes) >= 3 and partes[2] else None

    cantidad = None
    if cantidad_raw is not None:
        try:
            cantidad = int(float(cantidad_raw))
        except Exception:
            cantidad = None

    # Respaldo: si no se pudo leer el segundo campo, intenta encontrar cualquier número.
    if cantidad is None:
        encontrados = re.findall(r"-?\d+", texto)
        if encontrados:
            try:
                cantidad = int(encontrados[-1])
            except Exception:
                cantidad = None

    return {
        "texto_original": texto,
        "partes": partes,
        "num_op_mqtt": num_op,
        "cantidad_mqtt": cantidad,
        "actividad_mqtt": actividad,
    }


def agregar_marcaje_simulado(simulacion: dict[str, Any]) -> dict[str, Any]:
    valores = simulacion["base_datos"]["valores"]
    topic = valores.get("topic") or simulacion.get("mqtt", {}).get("topic")
    mac = _extraer_mac_desde_topic(topic)

    marcaje = {
        "id": str(uuid4()),
        "modo": "SIMULACION",
        "fecha_inicio": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "username": valores.get("username"),
        "codigo_usuario": valores.get("username"),
        "numOp": valores.get("numOp"),
        "descrip": valores.get("descrip"),
        "recurso": valores.get("recurso"),
        "actividad": valores.get("actividad"),
        "topic": topic,
        "mac": mac,
        "produccionUnidad": valores.get("produccionUnidad"),
        "conteo_simulado": 0,
        # Campos nuevos fase v8: asociación MQTT -> marcaje activo.
        "conteo_mqtt_actual": 0,
        "conteo_mqtt_anterior": None,
        "delta_ultimo_mensaje": 0,
        "mensajes_mqtt_asociados": 0,
        "ultimo_topic_mqtt": None,
        "ultimo_payload_mqtt": None,
        "ultimo_mqtt_fecha_hora": None,
        "ultimo_num_op_mqtt": None,
        "ultima_actividad_mqtt": None,
        "ultima_advertencia_mqtt": None,
    }

    _MARCAJES_ACTIVOS_SIMULADOS.append(marcaje)
    return marcaje


def cerrar_marcaje_simulado(marcaje_id: str) -> dict[str, Any] | None:
    for index, marcaje in enumerate(_MARCAJES_ACTIVOS_SIMULADOS):
        if marcaje["id"] == marcaje_id:
            return _MARCAJES_ACTIVOS_SIMULADOS.pop(index)

    return None


def asociar_mensaje_mqtt_a_marcaje(topic: str, payload: str, mac: str | None, tipo: str | None) -> dict[str, Any]:
    """
    Asocia un mensaje MQTT entrante con un marcaje activo simulado.

    Regla de esta fase:
    - Solo procesa topics tipo DATOS.
    - Busca un marcaje activo cuya MAC coincida.
    - Actualiza contadores en memoria.
    - NO inserta en BD.
    - NO cierra marcajes.
    """
    fecha_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if not mac:
        mac = _extraer_mac_desde_topic(topic)

    if not tipo:
        tipo = _extraer_tipo_desde_topic(topic)

    if tipo != "DATOS":
        return {
            "ok": False,
            "asociado": False,
            "motivo": "El topic no es de tipo DATOS; se recibió pero no se asocia a producción.",
            "topic": topic,
            "mac": mac,
            "tipo": tipo,
            "marcaje": None,
        }

    marcaje = next((m for m in _MARCAJES_ACTIVOS_SIMULADOS if m.get("mac") == mac), None)

    if marcaje is None:
        return {
            "ok": True,
            "asociado": False,
            "motivo": "No existe marcaje activo simulado para esta MAC.",
            "topic": topic,
            "mac": mac,
            "tipo": tipo,
            "marcaje": None,
        }

    datos_payload = _parsear_payload_datos(payload)
    cantidad = datos_payload.get("cantidad_mqtt")

    conteo_anterior = marcaje.get("conteo_mqtt_actual")
    delta = 0

    if isinstance(cantidad, int):
        if isinstance(conteo_anterior, int):
            delta = max(cantidad - conteo_anterior, 0)
        marcaje["conteo_mqtt_anterior"] = conteo_anterior
        marcaje["conteo_mqtt_actual"] = cantidad
        marcaje["delta_ultimo_mensaje"] = delta

    advertencias = []

    if datos_payload.get("num_op_mqtt") and str(datos_payload["num_op_mqtt"]) != str(marcaje.get("numOp")):
        advertencias.append(
            f"La OP del MQTT ({datos_payload['num_op_mqtt']}) no coincide con la OP del marcaje ({marcaje.get('numOp')})."
        )

    if datos_payload.get("actividad_mqtt") and str(datos_payload["actividad_mqtt"]) != str(marcaje.get("actividad")):
        advertencias.append(
            f"La actividad del MQTT ({datos_payload['actividad_mqtt']}) no coincide con la actividad del marcaje ({marcaje.get('actividad')})."
        )

    marcaje["mensajes_mqtt_asociados"] = int(marcaje.get("mensajes_mqtt_asociados") or 0) + 1
    marcaje["ultimo_topic_mqtt"] = topic
    marcaje["ultimo_payload_mqtt"] = payload
    marcaje["ultimo_mqtt_fecha_hora"] = fecha_hora
    marcaje["ultimo_num_op_mqtt"] = datos_payload.get("num_op_mqtt")
    marcaje["ultima_actividad_mqtt"] = datos_payload.get("actividad_mqtt")
    marcaje["ultima_advertencia_mqtt"] = " | ".join(advertencias) if advertencias else None

    return {
        "ok": True,
        "asociado": True,
        "motivo": "Mensaje MQTT asociado al marcaje activo simulado.",
        "topic": topic,
        "mac": mac,
        "tipo": tipo,
        "payload_parseado": datos_payload,
        "delta": delta,
        "advertencias": advertencias,
        "marcaje": marcaje,
        "marcajes": listar_marcajes_activos_simulados(),
    }


def agregar_o_actualizar_marcaje_estado(marcaje: dict[str, Any]) -> dict[str, Any]:
    """
    Agrega o actualiza un marcaje en el estado vivo compartido.
    Sirve para marcajes simulados y marcajes reales cargados desde BD.
    """
    marcaje_id = marcaje.get("id")

    for index, existente in enumerate(_MARCAJES_ACTIVOS_SIMULADOS):
        if existente.get("id") == marcaje_id:
            # Conserva contadores en vivo si ya existían y actualiza datos base.
            existente.update(marcaje)
            _MARCAJES_ACTIVOS_SIMULADOS[index] = existente
            return existente

    _MARCAJES_ACTIVOS_SIMULADOS.append(marcaje)
    return marcaje


def reemplazar_estado_marcajes(marcajes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Reemplaza completamente el estado vivo.
    Útil para sincronizar con smartfactory.marcajeactivo al iniciar o al refrescar.
    """
    _MARCAJES_ACTIVOS_SIMULADOS.clear()
    _MARCAJES_ACTIVOS_SIMULADOS.extend(marcajes)
    return listar_marcajes_activos_simulados()


def cerrar_marcaje_estado_por_id(marcaje_id: str) -> dict[str, Any] | None:
    return cerrar_marcaje_simulado(marcaje_id)

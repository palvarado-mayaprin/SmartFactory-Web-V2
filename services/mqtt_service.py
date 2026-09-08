import asyncio
import os
import threading
from typing import Any

from realtime.mqtt_websocket_manager import mqtt_ws_manager
from realtime.websocket_manager import manager as marcajes_ws_manager
from services.mqtt_estado_service import (
    actualizar_estado_mqtt,
    obtener_estado_mqtt,
    registrar_mensaje_mqtt,
)
from services.marcajes_estado_service import asociar_mensaje_mqtt_a_marcaje
from services.mqtt_persistencia_simulada_service import procesar_persistencia_mqtt

try:
    import paho.mqtt.client as mqtt
except ImportError:  # pragma: no cover
    mqtt = None

try:
    from db.conexion import dtbSmartFactory
except Exception:  # pragma: no cover
    dtbSmartFactory = None


class MqttMonitorService:
    """
    Servicio MQTT de lectura para SmartFactory Web.

    Esta fase es de validación segura:
    - se conecta al broker MQTT,
    - se suscribe a topics de lectura,
    - muestra mensajes en vivo por WebSocket,
    - calcula unidadesCalculadasConglomerado usando cantpliegos anterior por MAC,
    - arma INSERT IGNORE para mensajes_mqtt y datossensados,
    - ejecuta INSERT real solo si SMARTFACTORY_ENABLE_REAL_MQTT_DB_WRITES=1,
    - NO publica mensajes MQTT,
    - NO modifica marcajes reales.
    """

    def __init__(self) -> None:
        self.client: Any = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self.lock = threading.Lock()
        self.ejecutando = False
        self.suscripciones: list[str] = []

    def _crear_cliente(self):
        if mqtt is None:
            raise RuntimeError("No está instalado paho-mqtt. Ejecute: pip install paho-mqtt")

        # Compatible con paho-mqtt 1.x y 2.x
        try:
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
        except Exception:
            client = mqtt.Client()

        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_message = self._on_message
        client.on_log = self._on_log

        username = os.getenv("SMARTFACTORY_MQTT_USER", "mayaprin")
        password = os.getenv("SMARTFACTORY_MQTT_PASSWORD", "MayaPr24$")

        if username:
            client.username_pw_set(username=username, password=password)

        return client

    def _obtener_macs_desde_bd(self) -> list[str]:
        """
        Lee las MAC registradas en smartfactory.macdirectorio.
        Si falla la consulta, retorna lista vacía y el servicio solo queda con topics base.
        """
        if dtbSmartFactory is None:
            return []

        try:
            resultado = dtbSmartFactory("SELECT mac FROM smartfactory.macdirectorio").consultaSmartFactory()
            return [str(fila[0]).strip() for fila in resultado if fila and fila[0]]
        except Exception as error:
            actualizar_estado_mqtt(ultimo_error=f"No se pudieron consultar MACs: {error}")
            return []

    def _construir_suscripciones(self) -> list[str]:
        topics = ["conexion", "MAC"]

        for mac in self._obtener_macs_desde_bd():
            topics.extend([
                f"{mac}-CONFIG",
                f"{mac}-OP",
                f"{mac}-DATOS",
                f"{mac}-BANDERAS",
                f"{mac}-ALERT",
            ])

        # Eliminar duplicados manteniendo orden.
        return list(dict.fromkeys(topics))

    async def iniciar(self) -> dict[str, Any]:
        with self.lock:
            if self.ejecutando:
                return {
                    "ok": True,
                    "mensaje": "MQTT ya se encontraba ejecutando.",
                    "estado": obtener_estado_mqtt(),
                }

            self.loop = asyncio.get_running_loop()
            broker = os.getenv("SMARTFACTORY_MQTT_BROKER", "192.168.1.48")
            puerto = int(os.getenv("SMARTFACTORY_MQTT_PORT", "1883"))

            self.client = self._crear_cliente()
            self.suscripciones = self._construir_suscripciones()

            actualizar_estado_mqtt(
                ejecutando=True,
                conectado=False,
                broker=broker,
                puerto=puerto,
                suscripciones=self.suscripciones,
                ultimo_error=None,
            )

            try:
                self.client.connect(broker, puerto, keepalive=60)
                self.client.loop_start()
                self.ejecutando = True
            except Exception as error:
                self.ejecutando = False
                actualizar_estado_mqtt(ejecutando=False, conectado=False, ultimo_error=str(error))
                raise RuntimeError(f"No se pudo conectar al broker MQTT: {error}") from error

        await self._broadcast_estado("MQTT iniciando conexión.")
        return {
            "ok": True,
            "mensaje": "Servicio MQTT iniciado en modo lectura.",
            "estado": obtener_estado_mqtt(),
        }

    async def detener(self) -> dict[str, Any]:
        with self.lock:
            if self.client is not None:
                try:
                    self.client.loop_stop()
                    self.client.disconnect()
                except Exception:
                    pass

            self.client = None
            self.ejecutando = False
            actualizar_estado_mqtt(ejecutando=False, conectado=False)

        await self._broadcast_estado("MQTT detenido.")
        return {
            "ok": True,
            "mensaje": "Servicio MQTT detenido.",
            "estado": obtener_estado_mqtt(),
        }

    async def estado(self) -> dict[str, Any]:
        return {
            "ok": True,
            "estado": obtener_estado_mqtt(),
        }

    def _on_connect(self, client, userdata, flags, rc):
        conectado = rc == 0
        actualizar_estado_mqtt(conectado=conectado, ultimo_error=None if conectado else f"Código MQTT rc={rc}")

        if conectado:
            for topic in self.suscripciones:
                try:
                    client.subscribe(topic)
                except Exception as error:
                    actualizar_estado_mqtt(ultimo_error=f"Error suscribiendo {topic}: {error}")

            self._broadcast_desde_hilo({
                "tipo": "MQTT_ESTADO",
                "mensaje": "MQTT conectado y suscrito en modo lectura.",
                "estado": obtener_estado_mqtt(),
            })
        else:
            self._broadcast_desde_hilo({
                "tipo": "MQTT_ESTADO",
                "mensaje": f"MQTT no pudo conectar. Código rc={rc}",
                "estado": obtener_estado_mqtt(),
            })

    def _on_disconnect(self, client, userdata, rc):
        actualizar_estado_mqtt(conectado=False, ultimo_error=None if rc == 0 else f"Desconexión inesperada rc={rc}")
        self._broadcast_desde_hilo({
            "tipo": "MQTT_ESTADO",
            "mensaje": f"MQTT desconectado. rc={rc}",
            "estado": obtener_estado_mqtt(),
        })

    def _on_message(self, client, userdata, message):
        try:
            payload = message.payload.decode("utf-8", errors="replace")
        except Exception:
            payload = str(message.payload)

        topic = str(message.topic)
        mac = None
        tipo = None

        if len(topic) >= 17 and "-" in topic:
            partes = topic.split("-", 1)
            mac = partes[0]
            tipo = partes[1]

        mensaje = registrar_mensaje_mqtt(topic=topic, payload=payload, mac=mac, tipo=tipo)

        persistencia_simulada = procesar_persistencia_mqtt(
            topic=topic,
            payload=payload,
            mac=mac,
            tipo=tipo,
        )

        asociacion = asociar_mensaje_mqtt_a_marcaje(
            topic=topic,
            payload=payload,
            mac=mac,
            tipo=tipo,
        )

        # Adjuntamos el resultado de persistencia MQTT.
        # En modo protegido muestra SQL. En modo real también muestra resultado de ejecución.
        mensaje["persistencia_simulada"] = persistencia_simulada

        evento = {
            "tipo": "MQTT_MENSAJE_RECIBIDO",
            "mensaje": mensaje,
            "estado": obtener_estado_mqtt(),
            "asociacion": asociacion,
            "persistencia_simulada": persistencia_simulada,
        }

        self._broadcast_desde_hilo(evento)

        # Si el mensaje actualizó un marcaje activo, se notifica también al
        # WebSocket de marcajes para refrescar el sidebar en todas las pantallas.
        if asociacion.get("asociado"):
            self._broadcast_marcajes_desde_hilo({
                "tipo": "MARCAGES_ACTIVOS_ACTUALIZADOS",
                "mensaje": "MQTT asociado a marcaje activo simulado.",
                "marcajes": asociacion.get("marcajes", []),
                "marcaje": asociacion.get("marcaje"),
                "asociacion": asociacion,
            })


    def publicar(self, topic: str, payload: str) -> dict[str, Any]:
        """
        Publica un mensaje MQTT usando la conexión del servicio monitor.

        Se usa en v16 para enviar el inicio de marcaje al ESP.
        Requiere que el servicio MQTT esté iniciado/conectado desde la interfaz.
        """
        topic_limpio = str(topic or "").strip()
        payload_limpio = str(payload or "").strip()

        if not topic_limpio:
            return {"ok": False, "mensaje": "No se puede publicar MQTT: topic vacío."}

        if self.client is None or not self.ejecutando:
            return {
                "ok": False,
                "mensaje": "No se puede publicar MQTT: el servicio MQTT no está iniciado. Presione Conectar MQTT primero.",
                "topic": topic_limpio,
                "payload": payload_limpio,
            }

        try:
            info = self.client.publish(topic_limpio, payload_limpio)
            return {
                "ok": True,
                "mensaje": "Mensaje MQTT publicado correctamente.",
                "topic": topic_limpio,
                "payload": payload_limpio,
                "mid": getattr(info, "mid", None),
                "rc": getattr(info, "rc", None),
            }
        except Exception as error:
            return {
                "ok": False,
                "mensaje": f"Error publicando MQTT: {error}",
                "topic": topic_limpio,
                "payload": payload_limpio,
            }

    def _on_log(self, client, userdata, level, buf):
        # Se deja silencioso para no saturar terminal.
        pass

    async def _broadcast_estado(self, mensaje: str) -> None:
        await mqtt_ws_manager.broadcast({
            "tipo": "MQTT_ESTADO",
            "mensaje": mensaje,
            "estado": obtener_estado_mqtt(),
        })

    def _broadcast_desde_hilo(self, evento: dict[str, Any]) -> None:
        if self.loop is None:
            return

        try:
            asyncio.run_coroutine_threadsafe(mqtt_ws_manager.broadcast(evento), self.loop)
        except Exception:
            pass

    def _broadcast_marcajes_desde_hilo(self, evento: dict[str, Any]) -> None:
        if self.loop is None:
            return

        try:
            asyncio.run_coroutine_threadsafe(marcajes_ws_manager.broadcast(evento), self.loop)
        except Exception:
            pass


mqtt_monitor = MqttMonitorService()

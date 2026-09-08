from typing import Any

from fastapi import WebSocket


class MqttWebSocketManager:
    """
    Administra navegadores conectados al canal MQTT en vivo.

    Este canal es independiente del canal de marcajes activos para que el
    frontend pueda escuchar eventos MQTT sin mezclar responsabilidades.
    """

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        disconnected: list[WebSocket] = []

        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        for connection in disconnected:
            self.disconnect(connection)


mqtt_ws_manager = MqttWebSocketManager()

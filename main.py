import sys
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Permite importar módulos del proyecto actual: src/db/conexion.py
BASE_DIR = Path(__file__).resolve().parent
PROJECT_SRC = BASE_DIR.parent / "src"
if PROJECT_SRC.exists():
    sys.path.append(str(PROJECT_SRC))

from api.usuarios_api import router as usuarios_router
from api.ordenes_api import router as ordenes_router
from api.marcajes_api import router as marcajes_router
from api.mqtt_api import router as mqtt_router
from api.auth_api import router as auth_router
from realtime.websocket_manager import manager
from realtime.mqtt_websocket_manager import mqtt_ws_manager
from services.marcajes_estado_service import listar_marcajes_activos_simulados
from services.mqtt_service import mqtt_monitor

app = FastAPI(title="SmartFactory Web", version="20.22.0")

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

app.include_router(usuarios_router)
app.include_router(ordenes_router)
app.include_router(marcajes_router)
app.include_router(mqtt_router)
app.include_router(auth_router)


@app.on_event("startup")
async def iniciar_mqtt_automaticamente():
    """
    Inicia MQTT automáticamente al levantar el backend FastAPI.

    Antes el operador o administrador debía presionar el botón "Conectar MQTT".
    Como ese panel ahora queda reservado para ADMIN, el backend debe iniciar
    la lectura MQTT por sí solo para no afectar el flujo normal de planta.
    
    Si el broker no está disponible, no detenemos el arranque del backend:
    dejamos el error registrado en el estado MQTT para que pueda revisarse
    desde el panel administrador.
    """
    try:
        resultado = await mqtt_monitor.iniciar()
        print(resultado.get("mensaje", "MQTT iniciado automáticamente."))
    except Exception as error:
        print(f"No se pudo iniciar MQTT automáticamente: {error}")


@app.on_event("shutdown")
async def detener_mqtt_automaticamente():
    """
    Detiene MQTT ordenadamente cuando se apaga el backend FastAPI.
    """
    try:
        await mqtt_monitor.detener()
        print("MQTT detenido correctamente al cerrar backend.")
    except Exception as error:
        print(f"No se pudo detener MQTT correctamente: {error}")


@app.get("/", response_class=HTMLResponse)
def inicio(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html"
    )


@app.get("/api/health")
def health_check():
    return {"ok": True, "version": "20.22.0", "mensaje": "SmartFactory Web funcionando"}



@app.websocket("/ws/marcajes")
async def websocket_marcajes(websocket: WebSocket):
    """
    Canal en vivo para marcajes activos.

    Cada navegador conectado recibe actualizaciones cuando el backend
    modifica el estado simulado de marcajes activos.
    """
    await manager.connect(websocket)

    try:
        await websocket.send_json({
            "tipo": "MARCAGES_ACTIVOS_ACTUALIZADOS",
            "mensaje": "Conexión WebSocket establecida.",
            "marcajes": listar_marcajes_activos_simulados(),
        })

        while True:
            # Mantenemos viva la conexión.
            # En esta fase no necesitamos procesar mensajes enviados desde el frontend.
            await websocket.receive_text()

    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.websocket("/ws/mqtt")
async def websocket_mqtt(websocket: WebSocket):
    """
    Canal en vivo para mensajes MQTT recibidos por el backend.

    Esta fase transmite mensajes y puede persistir MQTT en BD si la variable de seguridad está activa.
    """
    from services.mqtt_estado_service import obtener_estado_mqtt

    await mqtt_ws_manager.connect(websocket)

    try:
        await websocket.send_json({
            "tipo": "MQTT_ESTADO",
            "mensaje": "Conexión WebSocket MQTT establecida.",
            "estado": obtener_estado_mqtt(),
        })

        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        mqtt_ws_manager.disconnect(websocket)

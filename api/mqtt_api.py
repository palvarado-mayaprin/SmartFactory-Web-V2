from fastapi import APIRouter, HTTPException

from services.mqtt_service import mqtt_monitor

router = APIRouter(prefix="/api/mqtt", tags=["mqtt"])


@router.post("/iniciar")
async def iniciar_mqtt():
    try:
        return await mqtt_monitor.iniciar()
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@router.post("/detener")
async def detener_mqtt():
    return await mqtt_monitor.detener()


@router.get("/estado")
async def estado_mqtt():
    return await mqtt_monitor.estado()

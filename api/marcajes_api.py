from fastapi import APIRouter, HTTPException

from models.schemas import PrepararMarcajeRequest,PrepararMarcajeImproductivoRequest ,ActivarMarcajeSimuladoRequest, CerrarMarcajeSimuladoRequest, SimularCierreMarcajeRequest
from services.marcajes_service import preparar_inicio_marcaje, simular_inicio_marcaje
from services.marcajes_estado_service import (
    agregar_marcaje_simulado,
    agregar_o_actualizar_marcaje_estado,
    cerrar_marcaje_estado_por_id,
    cerrar_marcaje_simulado,
    listar_marcajes_activos_simulados,
    reemplazar_estado_marcajes,
)
from services.persistencia_marcajes_service import (
    cerrar_marcaje_real_bd,
    esta_habilitada_escritura_real,
    esta_habilitada_publicacion_mqtt_real,
    iniciar_marcaje_real_bd,
    iniciar_marcaje_improductivo_bd,
    iniciar_relevo_mt_real_bd,
    listar_marcajes_activos_bd,
)
from realtime.websocket_manager import manager
from services.cierres_service import simular_cierre_marcaje, ejecutar_cierre_marcaje_real

router = APIRouter(prefix="/api/marcajes", tags=["Marcajes"])


@router.get("/modo-persistencia")
def api_modo_persistencia():
    escritura_bd = esta_habilitada_escritura_real()
    publicacion_mqtt = esta_habilitada_publicacion_mqtt_real()

    return {
        "ok": True,
        "escritura_real_habilitada": escritura_bd,
        "publicacion_mqtt_real_habilitada": publicacion_mqtt,
        "mensaje": (
            f"BD real: {'habilitada' if escritura_bd else 'protegida'} · "
            f"MQTT publish real: {'habilitado' if publicacion_mqtt else 'protegido'}"
        ),
    }


@router.post("/preparar-inicio")
def api_preparar_inicio_marcaje(payload: PrepararMarcajeRequest):
    resultado = preparar_inicio_marcaje(payload.model_dump())

    if not resultado["ok"]:
        raise HTTPException(status_code=400, detail=resultado["mensaje"])

    return resultado


@router.post("/simular-inicio")
def api_simular_inicio_marcaje(payload: PrepararMarcajeRequest):
    resultado = simular_inicio_marcaje(payload.model_dump())

    if not resultado["ok"]:
        raise HTTPException(status_code=400, detail=resultado["mensaje"])

    return resultado


@router.post("/iniciar-real-bd")
async def api_iniciar_marcaje_real_bd(payload: PrepararMarcajeRequest):
    resultado = iniciar_marcaje_real_bd(payload.model_dump())

    if not resultado["ok"]:
        # 409 porque no es error técnico: es bloqueo de modo protegido o validación operacional.
        raise HTTPException(status_code=409, detail=resultado)

    marcaje = resultado["marcaje"]
    agregar_o_actualizar_marcaje_estado(marcaje)
    marcajes = listar_marcajes_activos_simulados()

    await manager.broadcast({
        "tipo": "MARCAGES_ACTIVOS_ACTUALIZADOS",
        "mensaje": "Se insertó un marcaje real en BD.",
        "marcajes": marcajes,
        "marcaje": marcaje,
    })

    return {
        **resultado,
        "marcajes": marcajes,
    }
    
@router.post("/iniciar-improductivo")
async def api_iniciar_marcaje_real_bd(payload: PrepararMarcajeImproductivoRequest):
    resultado = iniciar_marcaje_improductivo_bd(payload.model_dump())

    if not resultado["ok"]:
        # 409 porque no es error técnico: es bloqueo de modo protegido o validación operacional.
        raise HTTPException(status_code=409, detail=resultado)

    marcaje = resultado["marcaje"]
    agregar_o_actualizar_marcaje_estado(marcaje)
    marcajes = listar_marcajes_activos_simulados()

    await manager.broadcast({
        "tipo": "MARCAGES_ACTIVOS_ACTUALIZADOS",
        "mensaje": "Se insertó un marcaje real en BD.",
        "marcajes": marcajes,
        "marcaje": marcaje,
    })

    return {
        **resultado,
        "marcajes": marcajes,
    }
    
@router.post("/iniciar-improductivo-bd")
async def api_iniciar_marcaje_improductivo_bd(payload: PrepararMarcajeRequest):
    resultado = iniciar_marcaje_real_bd(payload.model_dump())

    if not resultado["ok"]:
        # 409 porque no es error técnico: es bloqueo de modo protegido o validación operacional.
        raise HTTPException(status_code=409, detail=resultado)

    marcaje = resultado["marcaje"]
    agregar_o_actualizar_marcaje_estado(marcaje)
    marcajes = listar_marcajes_activos_simulados()

    await manager.broadcast({
        "tipo": "MARCAGES_ACTIVOS_ACTUALIZADOS",
        "mensaje": "Se insertó un marcaje real en BD.",
        "marcajes": marcajes,
        "marcaje": marcaje,
    })

    return {
        **resultado,
        "marcajes": marcajes,
    }




@router.post("/iniciar-relevo-mt-real")
async def api_iniciar_relevo_mt_real(payload: dict):
    """
    Abre un nuevo marcaje real para el siguiente operario después de un cierre MT.

    El frontend envía:
    - relevo: datos del marcaje cerrado con MT
    - codigo_usuario: usuario que toma el relevo
    """
    resultado = iniciar_relevo_mt_real_bd(payload)

    if not resultado["ok"]:
        raise HTTPException(status_code=409, detail=resultado)

    marcaje = resultado["marcaje"]
    agregar_o_actualizar_marcaje_estado(marcaje)
    marcajes = listar_marcajes_activos_simulados()

    await manager.broadcast({
        "tipo": "MARCAGES_ACTIVOS_ACTUALIZADOS",
        "mensaje": "Se abrió marcaje real por relevo MT.",
        "marcajes": marcajes,
        "marcaje": marcaje,
        "resultado_relevo": resultado,
    })

    return {
        **resultado,
        "marcajes": marcajes,
    }


@router.get("/activos-bd")
def api_listar_marcajes_activos_bd():
    return {
        "ok": True,
        "marcajes": listar_marcajes_activos_bd(),
    }


@router.post("/sincronizar-desde-bd")
async def api_sincronizar_marcajes_desde_bd():
    marcajes_bd = listar_marcajes_activos_bd()
    marcajes = reemplazar_estado_marcajes(marcajes_bd)

    await manager.broadcast({
        "tipo": "MARCAGES_ACTIVOS_ACTUALIZADOS",
        "mensaje": "Marcajes activos sincronizados desde smartfactory.marcajeactivo.",
        "marcajes": marcajes,
    })

    return {
        "ok": True,
        "mensaje": "Marcajes activos sincronizados desde BD.",
        "marcajes": marcajes,
    }


@router.get("/activos-simulados")
def api_listar_marcajes_activos_simulados():
    return {
        "ok": True,
        "marcajes": listar_marcajes_activos_simulados(),
    }


@router.post("/activar-simulacion")
async def api_activar_marcaje_simulado(payload: ActivarMarcajeSimuladoRequest):
    marcaje = agregar_marcaje_simulado(payload.simulacion)
    marcajes = listar_marcajes_activos_simulados()

    await manager.broadcast({
        "tipo": "MARCAGES_ACTIVOS_ACTUALIZADOS",
        "mensaje": "Se agregó un marcaje simulado.",
        "marcajes": marcajes,
        "marcaje": marcaje,
    })

    return {
        "ok": True,
        "mensaje": "Marcaje simulado agregado al estado en vivo.",
        "marcaje": marcaje,
        "marcajes": marcajes,
    }


@router.post("/cerrar-simulacion")
async def api_cerrar_marcaje_simulado(payload: CerrarMarcajeSimuladoRequest):
    marcaje = cerrar_marcaje_simulado(payload.marcaje_id)

    if not marcaje:
        raise HTTPException(status_code=404, detail="Marcaje simulado no encontrado.")

    marcajes = listar_marcajes_activos_simulados()

    await manager.broadcast({
        "tipo": "MARCAGES_ACTIVOS_ACTUALIZADOS",
        "mensaje": "Se cerró un marcaje simulado.",
        "marcajes": marcajes,
        "marcaje_cerrado": marcaje,
    })

    return {
        "ok": True,
        "mensaje": "Marcaje simulado cerrado.",
        "marcaje_cerrado": marcaje,
        "marcajes": marcajes,
    }


@router.post("/simular-cierre")
def api_simular_cierre_marcaje(payload: SimularCierreMarcajeRequest):
    resultado = simular_cierre_marcaje(
        marcaje=payload.marcaje,
        tipo_cierre=payload.tipo_cierre,
        total_usuario=payload.total_usuario,
    )

    if not resultado["ok"]:
        raise HTTPException(status_code=400, detail=resultado["mensaje"])

    return resultado


@router.post("/ejecutar-cierre-real")
async def api_ejecutar_cierre_marcaje_real(payload: SimularCierreMarcajeRequest):
    resultado = ejecutar_cierre_marcaje_real(
        marcaje=payload.marcaje,
        tipo_cierre=payload.tipo_cierre,
        total_usuario=payload.total_usuario,
    )

    if not resultado["ok"]:
        raise HTTPException(status_code=409, detail=resultado)

    marcaje = resultado.get("marcaje_cerrado") or payload.marcaje
    cerrar_marcaje_estado_por_id(marcaje.get("id"))
    marcajes = listar_marcajes_activos_simulados()

    await manager.broadcast({
        "tipo": "MARCAGES_ACTIVOS_ACTUALIZADOS",
        "mensaje": "Se ejecutó cierre real de marcaje.",
        "marcajes": marcajes,
        "marcaje_cerrado": marcaje,
        "resultado_cierre": resultado,
    })

    return {
        **resultado,
        "marcajes": marcajes,
    }


@router.post("/cerrar-real-bd")
async def api_cerrar_marcaje_real_bd(payload: dict):
    marcaje = payload.get("marcaje") or {}

    if not marcaje:
        raise HTTPException(status_code=400, detail="Debe enviar el objeto marcaje a cerrar.")

    resultado = cerrar_marcaje_real_bd(marcaje)

    if not resultado["ok"]:
        raise HTTPException(status_code=409, detail=resultado)

    cerrar_marcaje_estado_por_id(marcaje.get("id"))
    marcajes = listar_marcajes_activos_simulados()

    await manager.broadcast({
        "tipo": "MARCAGES_ACTIVOS_ACTUALIZADOS",
        "mensaje": "Se cerró un marcaje real en BD.",
        "marcajes": marcajes,
        "marcaje_cerrado": marcaje,
    })

    return {
        **resultado,
        "marcajes": marcajes,
    }

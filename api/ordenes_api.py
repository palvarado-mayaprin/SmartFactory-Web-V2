from fastapi import APIRouter, HTTPException

from models.schemas import BuscarOpRequest, ActividadesRequest, BuscarRecursosImproductivoRequest
from services.ordenes_service import buscar_orden_produccion,buscar_recursos_improductivo ,obtener_actividades_por_recurso, obtener_actividades_no_cotizadas_por_recurso

router = APIRouter(prefix="/api", tags=["Ordenes"])


@router.post("/op/buscar")
def api_buscar_op(payload: BuscarOpRequest):
    resultado = buscar_orden_produccion(
        num_op=payload.num_op,
        codigo_usuario=payload.codigo_usuario
    )

    if not resultado["ok"]:
        raise HTTPException(status_code=400, detail=resultado["mensaje"])

    return resultado

@router.post("/op/buscarRecursosExistentes")
def api_buscar_op(payload: BuscarRecursosImproductivoRequest):
    resultado = buscar_recursos_improductivo(
        codigo_usuario=payload.codigo_usuario
    )

    if not resultado["ok"]:
        raise HTTPException(status_code=400, detail=resultado["mensaje"])

    return resultado


@router.post("/actividades/recurso")
def api_actividades_por_recurso(payload: ActividadesRequest):
    actividades = obtener_actividades_por_recurso(
        num_ot=payload.num_ot,
        recurso=payload.recurso
    )

    return {
        "ok": True,
        "actividades": actividades
    }


@router.post("/actividades/no-cotizadas")
def api_actividades_no_cotizadas_por_recurso(payload: ActividadesRequest):
    actividades = obtener_actividades_no_cotizadas_por_recurso(
        num_ot=payload.num_ot,
        recurso=payload.recurso
    )

    return {
        "ok": True,
        "actividades": actividades
    }

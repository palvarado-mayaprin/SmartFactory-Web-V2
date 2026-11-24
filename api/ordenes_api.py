from fastapi import APIRouter, HTTPException

from models.schemas import BuscarOpRequest, ActividadesRequest, BuscarRecursosImproductivoRequest, OtsActividadRequest
from services.ordenes_service import buscar_orden_produccion,buscar_recursos_improductivo ,obtener_actividades_por_recurso, obtener_actividades_no_cotizadas_por_recurso
from services.resolucion_ot_service import resolver_desde_optimus

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

@router.post("/op/ots")
def api_ots_de_actividad(payload: OtsActividadRequest):
    """Solo lectura: indica si el operario debe elegir OT (docs/ai/14-resolucion-ot.md §2.3)."""
    resultado = resolver_desde_optimus(payload.num_op, payload.actividad)

    if resultado["ok"]:
        return {"ok": True, "requiereEleccion": False, "ots": []}
    if resultado["codigo"] == "SELECCION_OT_REQUERIDA":
        return {"ok": True, "requiereEleccion": True, "ots": resultado["ots_candidatas"]}

    estado = 503 if resultado["codigo"] == "OPTIMUS_NO_DISPONIBLE" else 409
    raise HTTPException(status_code=estado, detail=resultado)


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
        num_op=payload.num_op,
        recurso=payload.recurso
    )

    return {
        "ok": True,
        "actividades": actividades
    }


@router.post("/actividades/no-cotizadas")
def api_actividades_no_cotizadas_por_recurso(payload: ActividadesRequest):
    actividades = obtener_actividades_no_cotizadas_por_recurso(
        num_op=payload.num_op,
        recurso=payload.recurso
    )

    return {
        "ok": True,
        "actividades": actividades
    }

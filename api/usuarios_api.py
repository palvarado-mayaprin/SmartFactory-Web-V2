from fastapi import APIRouter, HTTPException

from models.schemas import IdentificarRequest
from services.usuarios_service import identificar_usuario_prueba, consultar_marcaje_activo

router = APIRouter(prefix="/api/usuario", tags=["Usuarios"])


@router.post("/identificar-prueba")
def api_identificar_prueba(payload: IdentificarRequest):
    usuario = identificar_usuario_prueba(payload.codigo_usuario)

    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado o descontinuado")

    marcaje_activo = consultar_marcaje_activo(usuario["code"])

    return {
        "ok": True,
        "usuario": usuario,
        "marcaje_activo": marcaje_activo,
        "siguiente_paso": "cerrar_marcaje" if marcaje_activo else "ingresar_op"
    }

from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from services.auth_service import validar_usuario_elevado


router = APIRouter(prefix="/api/auth", tags=["Autenticación"])


class UsuarioElevadoRequest(BaseModel):
    username: str
    password: str


@router.post("/usuario-elevado")
def api_usuario_elevado(payload: UsuarioElevadoRequest):
    usuario = validar_usuario_elevado(payload.username, payload.password)

    if not usuario:
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")

    tipo_usuario = usuario.get("tipo_usuario", "NO")

    if tipo_usuario == "NO":
        raise HTTPException(status_code=403, detail="El usuario no tiene permisos elevados")

    return {
        "ok": True,
        "usuario_elevado": usuario,
        "tipo_usuario": tipo_usuario,
        "mensaje": "Acceso concedido.",
    }

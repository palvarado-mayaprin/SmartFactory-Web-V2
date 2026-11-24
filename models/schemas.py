from typing import Annotated

from pydantic import BaseModel, Field


class IdentificarRequest(BaseModel):
    codigo_usuario: str = Field(..., min_length=1, description="Código de usuario, ejemplo: M2013")


class BuscarOpRequest(BaseModel):
    num_op: str = Field(..., min_length=1, description="Número de OP ingresado por el usuario")
    codigo_usuario: str = Field(..., min_length=1, description="Usuario identificado previamente")
    
    
class BuscarRecursosImproductivoRequest(BaseModel):
    codigo_usuario: str = Field(..., min_length=1, description="Usuario identificado previamente")


class ActividadesRequest(BaseModel):
    num_op: str = Field(..., pattern=r"^[0-9]+$", description="Número de OP (j_number / wo_job), solo dígitos")
    recurso: str = Field(..., min_length=1, description="Centro de costo/recurso seleccionado")


class OtsActividadRequest(BaseModel):
    num_op: str = Field(..., pattern=r"^[0-9]+$", description="Número de OP (j_number / wo_job), solo dígitos")
    actividad: str = Field(..., pattern=r"\S", description="Código de actividad (tk_code)")


class UltimoResumenRecursoUsuarioRequest(BaseModel):
    recurso: str = Field(..., min_length=1, description="Recurso del marcaje improductivo que se está cerrando")
    username: str = Field(..., min_length=1, description="Usuario del marcaje improductivo que se está cerrando")


class PrepararMarcajeRequest(BaseModel):
    num_op: str = Field(..., min_length=1, description="Número de OP real/job")
    # 2026-11-24: la OT se resuelve en el servidor; los campos extra que envíe el navegador se ignoran.
    numero_ot: int | None = Field(None, ge=1, description="OT elegida por el operario cuando la actividad está en varias OT")
    descripcion: str = Field(..., min_length=1, description="Descripción de la orden")
    cantidad: str | int | float = Field(..., description="Cantidad cotizada")
    recurso: str = Field(..., min_length=1, description="Centro de costo/recurso")
    actividad: str = Field(..., min_length=1, description="Código de actividad")
    actividad_nombre: str = Field(..., min_length=1, description="Nombre de actividad")
    codigo_usuario: str = Field(..., min_length=1, description="Código del trabajador")
    
    
class PrepararMarcajeImproductivoRequest(BaseModel):
    num_op: str = Field(..., min_length=1, description="Número de OP real/job")
    cantidad: str | int | float = Field(..., description="Cantidad cotizada")
    descripcion: str = Field(..., min_length=1, description="Descripción de la orden")
    recurso: str = Field(..., min_length=1, description="Centro de costo/recurso")
    actividad: str = Field(..., min_length=1, description="Código de actividad")
    actividad_nombre: str = Field(..., min_length=1, description="Nombre de actividad")
    codigo_usuario: str = Field(..., min_length=1, description="Código del trabajador")


class ActivarMarcajeSimuladoRequest(BaseModel):
    simulacion: dict = Field(..., description="Objeto de simulación generado por /api/marcajes/simular-inicio")


class CerrarMarcajeSimuladoRequest(BaseModel):
    marcaje_id: str = Field(..., min_length=1, description="ID del marcaje simulado a cerrar")


class SimularCierreMarcajeRequest(BaseModel):
    marcaje: dict = Field(..., description="Objeto marcaje activo que se desea cerrar")
    tipo_cierre: str = Field(..., min_length=1, description="FINAL, MD o MT")
    total_usuario: str | int | float | None = Field(0, description="Cantidad manual reportada por el usuario")
    pausa_improductiva: bool = Field(False, description="True solo cuando el cierre MD proviene del botón PAUSA POR ACTIVIDAD IMPRODUCTIVA")
    # v20.24: opcional para mantener compatibilidad con clientes anteriores (omitido = NULL, no registrado).
    pliegos_incorrectos: Annotated[int, Field(strict=True, ge=0, le=2_147_483_647)] | None = Field(
        None,
        description="Pliegos incorrectos o rechazados declarados por el operario (entero >= 0). Independiente de total_usuario y cantidadreal.",
    )

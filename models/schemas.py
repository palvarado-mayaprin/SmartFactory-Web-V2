from pydantic import BaseModel, Field


class IdentificarRequest(BaseModel):
    codigo_usuario: str = Field(..., min_length=1, description="Código de usuario, ejemplo: M2013")


class BuscarOpRequest(BaseModel):
    num_op: str = Field(..., min_length=1, description="Número de OP ingresado por el usuario")
    codigo_usuario: str = Field(..., min_length=1, description="Usuario identificado previamente")
    
    
class BuscarRecursosImproductivoRequest(BaseModel):
    codigo_usuario: str = Field(..., min_length=1, description="Usuario identificado previamente")


class ActividadesRequest(BaseModel):
    num_ot: str = Field(..., min_length=1, description="Número OT completo usado en wo_number/tk_wonum")
    recurso: str = Field(..., min_length=1, description="Centro de costo/recurso seleccionado")


class PrepararMarcajeRequest(BaseModel):
    num_op: str = Field(..., min_length=1, description="Número de OP real/job")
    num_ot: str = Field(..., min_length=1, description="Número OT, normalmente OP + 01")
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

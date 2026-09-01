from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CriteriosValoracion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    precio: int = Field(ge=1, le=5)
    calidad: int = Field(ge=1, le=5)
    atencion: int = Field(ge=1, le=5)
    puntualidad: int = Field(ge=1, le=5)


class CalificacionesComentariosIn(BaseModel):
    puntuacion_global: int = Field(ge=1, le=5)
    criterios: CriteriosValoracion
    comentario: str | None = Field(default=None, max_length=1000)


class SolicitudResenaCreate(BaseModel):
    contacto_referencia_cliente: str = Field(min_length=3, max_length=100)


class SolicitudResenaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_solicitud: int
    oferente_id: int
    codigo_unico: str
    contacto_referencia_cliente: str
    estado: str
    fecha_generacion: datetime
    fecha_expiracion: datetime | None = None


class ResenaCreate(BaseModel):
    codigo_unico: str
    nombre_cliente: str = Field(min_length=2, max_length=100)
    contacto_cliente_ingresado: str = Field(min_length=3, max_length=100)
    calificaciones_comentarios: CalificacionesComentariosIn


class ResenaModeracion(BaseModel):
    aprobar: bool


class ResenaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_resena: int
    oferente_id: int
    solicitud_id: int
    nombre_cliente: str
    calificaciones_comentarios: dict
    estado: str
    fecha_creacion: datetime


class ResenaAdminOut(ResenaOut):
    contacto_cliente_ingresado: str

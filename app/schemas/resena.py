from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SolicitudResenaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_solicitud: int
    oferente_id: int
    codigo_unico: str
    estado: str
    fecha_generacion: datetime
    fecha_expiracion: datetime | None = None


class ResenaCreate(BaseModel):
    codigo_unico: str
    nombre_cliente: str
    contacto_cliente_ingresado: str
    calificacion: int = Field(ge=1, le=5)
    comentario: str | None = None


class ResenaModeracion(BaseModel):
    aprobar: bool
    replica_oferente: str | None = None


class ResenaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_resena: int
    oferente_id: int
    solicitud_id: int
    nombre_cliente: str
    calificacion: int
    comentario: str | None = None
    estado: str
    replica_oferente: str | None = None
    fecha_creacion: datetime


class ResenaAdminOut(ResenaOut):
    contacto_cliente_ingresado: str

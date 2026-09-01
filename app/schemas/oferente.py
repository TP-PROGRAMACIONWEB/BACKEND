from datetime import time
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class OferenteBase(BaseModel):
    nombre: str
    apellido: str
    dni_cuit: str
    telefono: str
    categoria_id: int | None = None
    numero_matricula: str | None = None
    latitud: Decimal | None = None
    longitud: Decimal | None = None
    radio_cobertura_km: Decimal | None = None
    hora_inicio_atencion: time | None = None
    hora_fin_atencion: time | None = None
    disponible_emergencia: bool = False
    descripcion: str | None = None


class OferenteCreate(OferenteBase):
    pass


class OferenteUpdate(BaseModel):
    nombre: str | None = None
    apellido: str | None = None
    telefono: str | None = None
    categoria_id: int | None = None
    numero_matricula: str | None = None
    latitud: Decimal | None = None
    longitud: Decimal | None = None
    radio_cobertura_km: Decimal | None = None
    hora_inicio_atencion: time | None = None
    hora_fin_atencion: time | None = None
    disponible_emergencia: bool | None = None
    descripcion: str | None = None


class OferenteOut(OferenteBase):
    model_config = ConfigDict(from_attributes=True)

    id_oferente: int
    id_usuario: int
    estado_verificacion: str
    promedio_calificacion: Decimal
    cantidad_resenas_rechazadas: int

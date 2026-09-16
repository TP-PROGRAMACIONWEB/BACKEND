import re
from datetime import time
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

DNI_CUIT_RE = re.compile(r"^[0-9-]{6,50}$")
TELEFONO_RE = re.compile(r"^[0-9+\s]{6,50}$")


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

    @field_validator("dni_cuit")
    @classmethod
    def validar_dni_cuit(cls, value: str) -> str:
        if not DNI_CUIT_RE.match(value):
            raise ValueError("DNI/CUIT inválido: solo se permiten dígitos y guiones")
        return value

    @field_validator("telefono")
    @classmethod
    def validar_telefono(cls, value: str) -> str:
        if not TELEFONO_RE.match(value):
            raise ValueError("Teléfono inválido: solo se permiten dígitos, espacios y '+'")
        return value


class OferenteCreate(OferenteBase):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "nombre": "Juan",
                "apellido": "Pérez",
                "dni_cuit": "20-30111222-3",
                "telefono": "+54 3564 400111",
                "categoria_id": 1,
                "numero_matricula": "EL-12345",
                "disponible_emergencia": True,
                "descripcion": "Electricista matriculado, más de 10 años de experiencia.",
            }
        }
    )


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

    @field_validator("telefono")
    @classmethod
    def validar_telefono(cls, value: str | None) -> str | None:
        if value is not None and not TELEFONO_RE.match(value):
            raise ValueError("Teléfono inválido: solo se permiten dígitos, espacios y '+'")
        return value


class OferenteOut(OferenteBase):
    model_config = ConfigDict(from_attributes=True)

    id_oferente: int
    estado_verificacion: str
    promedio_calificacion: Decimal
    cantidad_rechazos_acumulados: int

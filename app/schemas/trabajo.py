from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_core import PydanticCustomError

from app.core.config import settings


class TrabajoCreate(BaseModel):
    """Body de `POST /api/v1/oferentes/me/trabajos` (HU-04 T06, D13).

    `titulo` y `descripcion` son obligatorios. `fotos` son los paths que devolvió
    la subida, **en el orden de carga**: la primera es la foto principal (caso A50).
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "titulo": "Cambio de disyuntor",
                "descripcion": "Reemplazo del disyuntor diferencial del tablero principal.",
                "fotos": ["oferentes/7/trabajo/ab12cd34ef56ab12cd34ef56ab12cd34.jpg"],
            }
        },
    )

    titulo: str = Field(min_length=1, max_length=100, description="Obligatorio. Entre 1 y 100 caracteres.")
    descripcion: str = Field(min_length=10, max_length=1000, description="Obligatoria. Entre 10 y 1000 caracteres.")
    fotos: list[str] = Field(description="Entre 1 y 5 paths, en el orden en que se cargaron.")

    @field_validator("fotos")
    @classmethod
    def validar_fotos(cls, valor: list[str]) -> list[str]:
        if not valor:
            raise PydanticCustomError("fotos_requeridas", "Cargá al menos una foto del trabajo")
        if len(valor) > settings.fotos_por_trabajo_maximas:
            raise PydanticCustomError("demasiadas_fotos", f"Un trabajo admite hasta {settings.fotos_por_trabajo_maximas} fotos")
        if len(set(valor)) != len(valor):
            raise PydanticCustomError("fotos_duplicadas", "La misma foto no puede cargarse dos veces en un trabajo")
        return valor


class FotoTrabajoOut(BaseModel):
    orden: int = Field(description="Posición de la foto dentro del trabajo, desde 1.")
    url: str


class TrabajoOut(BaseModel):
    id_trabajo: int
    titulo: str
    descripcion: str
    fecha_creacion: datetime
    foto_principal_url: str | None = Field(default=None, description="Foto con orden 1. Es la que muestra la tarjeta.")
    fotos: list[FotoTrabajoOut] = Field(default_factory=list, description="Todas las fotos ordenadas. Alimenta el carrusel.")



from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TipoImagenLiteral = Literal["Perfil", "Portada", "Trabajo"]


class SubidaIn(BaseModel):
    """Paso 1 de la subida: el navegador declara qué va a subir. Lo que cuenta
    al confirmar es lo que reporta Storage, no esto."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"tipo": "Perfil", "content_type": "image/jpeg", "tamano_bytes": 1048576}},
    )

    tipo: TipoImagenLiteral
    content_type: str = Field(description="image/jpeg o image/png.")
    tamano_bytes: int = Field(description="Tamaño del archivo en bytes. Máximo 5 MB.")


class ArchivoRefIn(BaseModel):
    """Body de la confirmación de foto de perfil o portada (paso 3)."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"path": "oferentes/7/perfil/ab12cd34ef56ab12cd34ef56ab12cd34.jpg"}},
    )

    path: str = Field(description="El path que devolvió el paso 1.")


class SubidaOut(BaseModel):
    path: str = Field(description="Clave del objeto en el bucket. Se devuelve al confirmar.")
    upload_url: str = Field(description="URL firmada a la que se hace el PUT del archivo.")
    tipo: str
    content_type: str


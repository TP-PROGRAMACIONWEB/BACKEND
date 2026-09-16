from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.services.matriculas import DIGITOS_POR_TIPO

TipoProfesionalLiteral = Literal["Gasista", "Aire acondicionado"]


class ValidacionMatriculaIn(BaseModel):
    """Datos del bloque de fidelización del perfil: el botón Confirmar se
    habilita recién con los dos campos completos y la cantidad de dígitos
    correcta para el tipo elegido."""

    model_config = ConfigDict(json_schema_extra={"example": {"tipo_profesional": "Gasista", "numero_matricula": "1000008919"}})

    tipo_profesional: TipoProfesionalLiteral
    numero_matricula: str = Field(description="Solo dígitos. 10 para Gasista, 9 para Aire acondicionado.")

    @model_validator(mode="after")
    def validar_numero(self):
        numero = self.numero_matricula.strip()
        if not numero.isdigit():
            raise ValueError("El número de matrícula solo puede tener dígitos")
        esperados = DIGITOS_POR_TIPO[self.tipo_profesional]
        if len(numero) != esperados:
            raise ValueError(f"El número de matrícula de {self.tipo_profesional} debe tener {esperados} dígitos")
        self.numero_matricula = numero
        return self


class MatriculaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_matricula: int
    tipo_profesional: str
    numero_matricula: str
    categoria: str
    fecha_vencimiento: date
    fecha_fidelizacion: datetime


class ValidacionMatriculaOut(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {"resultado": "Validada", "mensaje": "Su matrícula fue fidelizada exitosamente"}})

    resultado: str = Field(
        description="Validada | No_Encontrada | Timeout | Ya_Fidelizada | Reemplazo_Solicitado | Vencida | Nombre_No_Coincide"
    )
    mensaje: str
    matricula: MatriculaOut | None = Field(default=None, description="La matrícula vigente del oficio, si ya hay una fidelizada.")


class ValidacionHistorialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_validacion: int
    tipo_profesional: str
    numero_matricula: str
    resultado: str
    estado_reemplazo: str | None = Field(default=None, description="Solo cuando resultado = Reemplazo_Solicitado.")
    fecha_intento: datetime


class ReemplazoResolucionIn(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {"autorizar": True}})

    autorizar: bool = Field(description="true = autoriza el reemplazo; false = lo deniega.")


class ReemplazoResueltoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_validacion: int
    estado_reemplazo: str
    matricula: MatriculaOut | None = None

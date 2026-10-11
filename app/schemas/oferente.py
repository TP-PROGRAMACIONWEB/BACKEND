import re
from datetime import time
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, ValidationInfo, field_validator, model_validator
from pydantic_core import PydanticCustomError

from app.core.catalogos import DIAS_VALIDOS, ETIQUETA_EXPERIENCIA
from app.services.mensajes import normalizar_telefono, telefono_es_valido

NOMBRE_RE = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ .'&-]+")
DIGITOS_RE = re.compile(r"[0-9]+")
PESOS_CUIT = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)


def _vacio_a_none(valor):
    """Texto opcional: cadena vacía o solo espacios se guardan como NULL (caso A17)."""
    if isinstance(valor, str):
        valor = valor.strip()
        return valor or None
    return valor


TextoOpcional = Annotated[str | None, BeforeValidator(_vacio_a_none)]


def cuit_valido(cuit: str) -> bool:
    """Dígito verificador del CUIT (módulo 11). El resultado 10 no existe."""
    suma = sum(int(digito) * peso for digito, peso in zip(cuit[:10], PESOS_CUIT))
    verificador = 11 - suma % 11
    if verificador == 11:
        verificador = 0
    return verificador != 10 and verificador == int(cuit[10])


def normalizar_dni_cuit(valor: str) -> str:
    """Quita guiones y puntos; quedan 7, 8 u 11 dígitos. Se guarda solo el número."""
    limpio = valor.replace("-", "").replace(".", "")
    if not DIGITOS_RE.fullmatch(limpio) or len(limpio) not in (7, 8, 11):
        raise PydanticCustomError("dni_cuit_invalido", "Debe ingresar un formato válido en el campo DNI/CUIT")
    if len(limpio) == 11 and not cuit_valido(limpio):
        raise PydanticCustomError("dni_cuit_invalido", "Debe ingresar un formato válido en el campo DNI/CUIT")
    return limpio


def _validar_media_hora(valor: time) -> time:
    if valor.minute not in (0, 30) or valor.second or valor.microsecond:
        raise PydanticCustomError("horario_invalido", "El horario tiene que ser en punto o y media")
    return valor


class _DatosOferente(BaseModel):
    """Campos del formulario de registro y de la edición. Acá todos son
    opcionales; el registro los vuelve obligatorios en la subclase.

    El correo no viaja en el body (D6): si llega, se descarta.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    nombre: str | None = Field(default=None, min_length=2, max_length=150)
    telefono: str | None = None
    categoria_id: int | None = None
    especialidad: TextoOpcional = Field(default=None, max_length=100)
    experiencia: TextoOpcional = None
    dias_atencion: list[int] | None = None
    hora_inicio_atencion: time | None = None
    hora_fin_atencion: time | None = None
    disponible_emergencia: bool | None = None
    info_guardia: TextoOpcional = Field(default=None, max_length=200)

    @model_validator(mode="before")
    @classmethod
    def descartar_correo(cls, datos):
        if isinstance(datos, dict) and "email" in datos:
            return {clave: valor for clave, valor in datos.items() if clave != "email"}
        return datos

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, valor: str | None) -> str | None:
        if valor is not None and not NOMBRE_RE.fullmatch(valor):
            raise PydanticCustomError("nombre_invalido", "Solo se permiten letras, espacios, punto, apóstrofe, guion y &")
        return valor

    @field_validator("telefono")
    @classmethod
    def validar_telefono(cls, valor: str | None) -> str | None:
        if valor is None:
            return valor
        if not telefono_es_valido(valor):
            raise PydanticCustomError("telefono_invalido", "Ingresa 10 dígitos, con guion opcional. Sin 0, 15 o +54 al inicio.")
        return normalizar_telefono(valor)

    @field_validator("experiencia")
    @classmethod
    def validar_experiencia(cls, valor: str | None) -> str | None:
        if valor is not None and valor not in ETIQUETA_EXPERIENCIA:
            raise PydanticCustomError("experiencia_invalida", "Seleccioná un rango de experiencia de la lista")
        return valor

    @field_validator("dias_atencion")
    @classmethod
    def validar_dias(cls, valor: list[int] | None) -> list[int] | None:
        if valor is None:
            return valor
        if not valor:
            raise PydanticCustomError("dias_requeridos", "Complete este campo")
        if any(dia not in DIAS_VALIDOS for dia in valor) or len(set(valor)) != len(valor):
            raise PydanticCustomError("dias_invalidos", "Los días tienen que ser únicos y estar entre lunes (1) y domingo (7)")
        return sorted(valor)

    @field_validator("hora_inicio_atencion")
    @classmethod
    def validar_inicio(cls, valor: time | None) -> time | None:
        return _validar_media_hora(valor) if valor is not None else valor

    @field_validator("hora_fin_atencion")
    @classmethod
    def validar_fin(cls, valor: time | None, info: ValidationInfo) -> time | None:
        if valor is None:
            return valor
        _validar_media_hora(valor)
        inicio = info.data.get("hora_inicio_atencion")
        if inicio is not None and valor <= inicio:
            raise PydanticCustomError("horario_invalido", "El horario de cierre tiene que ser posterior a la apertura")
        return valor


class OferenteRegistro(_DatosOferente):
    """Body de `POST /api/v1/oferentes` (HU-04, CA02 y CA03)."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "nombre": "Serena Ludueña",
                "dni_cuit": "27-30111222-6",
                "telefono": "3564-400111",
                "categoria_id": 1,
                "especialidad": "Instalaciones domiciliarias",
                "experiencia": "3_A_5",
                "dias_atencion": [1, 2, 3, 4, 5],
                "hora_inicio_atencion": "08:00",
                "hora_fin_atencion": "18:00",
                "disponible_emergencia": True,
                "info_guardia": "Atiendo urgencias de lunes a sábado hasta las 22 h.",
            }
        },
    )

    nombre: str = Field(min_length=2, max_length=150, description="Nombre y apellido, o razón social. Un solo campo.")
    dni_cuit: str = Field(description="7 u 8 dígitos (DNI) o 11 con dígito verificador (CUIT). Guiones y puntos opcionales.")
    telefono: str = Field(description="10 dígitos con guion opcional. Sin 0, 15 ni +54.")
    categoria_id: int = Field(description="Categoría u oficio principal, activa.")
    dias_atencion: list[int] = Field(description="Días ISO: 1 = lunes … 7 = domingo. Al menos uno.")
    hora_inicio_atencion: time = Field(description="HH:MM, minutos 00 o 30.")
    hora_fin_atencion: time = Field(description="HH:MM, minutos 00 o 30, posterior a la apertura.")
    disponible_emergencia: bool = False

    @field_validator("dni_cuit")
    @classmethod
    def validar_dni_cuit(cls, valor: str) -> str:
        return normalizar_dni_cuit(valor)

    @model_validator(mode="after")
    def guardia_solo_con_emergencia(self):
        # Caso A17: si el toggle está apagado, el texto de guardia no se guarda.
        if not self.disponible_emergencia:
            self.info_guardia = None
        return self


class OferenteEdicion(_DatosOferente):
    """Body de `PUT /api/v1/oferentes/me` (caso A33, D18). Todo opcional y sin
    DNI/CUIT: ese dato no se cambia después del registro."""

    descripcion: TextoOpcional = None
    latitud: Decimal | None = None
    longitud: Decimal | None = None
    radio_cobertura_km: Decimal | None = None


# --- Salidas ----------------------------------------------------------------


class CategoriaRef(BaseModel):
    id_categoria: int
    nombre: str


class ExperienciaRef(BaseModel):
    codigo: str
    etiqueta: str


class MatriculaRef(BaseModel):
    tipo_profesional: str
    numero_matricula: str


class OferentePublicoOut(BaseModel):
    """Perfil público (CA04, D7): todo menos DNI/CUIT, estado de verificación y
    rechazos acumulados. Las horas van como "HH:MM"."""

    id_oferente: int
    nombre: str
    categoria_id: int | None = None
    categoria: CategoriaRef | None = None
    especialidad: str | None = None
    experiencia: ExperienciaRef | None = None
    telefono: str
    email: str = Field(description="El mismo correo con el que el Profesional entra (D6). Es público por D7.")
    dias_atencion: list[int] = Field(default_factory=list)
    hora_inicio_atencion: str | None = None
    hora_fin_atencion: str | None = None
    disponible_emergencia: bool
    info_guardia: str | None = None
    descripcion: str | None = None
    latitud: Decimal | None = None
    longitud: Decimal | None = None
    radio_cobertura_km: Decimal | None = None
    promedio_calificacion: Decimal
    cantidad_resenas: int = Field(description="Reseñas aceptadas. Es el contador de la pestaña Opiniones.")
    cantidad_trabajos: int = Field(description="Trabajos realizados cargados. Con 5, el frontend oculta el alta.")
    tiene_matricula_validada: bool = Field(default=False, description="HU-02: true con al menos una matrícula fidelizada.")
    matriculas: list[MatriculaRef] = Field(default_factory=list)
    foto_perfil_url: str | None = None
    portada_url: str | None = None


class OferentePrivadoOut(OferentePublicoOut):
    """Perfil del dueño (`GET /oferentes/me`): suma lo que nadie más ve."""

    dni_cuit: str
    estado_verificacion: str
    cantidad_rechazos_acumulados: int = Field(description="Dato interno de moderación; no se expone al público.")

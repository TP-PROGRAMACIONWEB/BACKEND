from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.services.mensajes import normalizar_telefono, telefono_es_valido


class CriteriosValoracion(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"precio": 4, "calidad": 5, "atencion": 4.5, "puntualidad": 4.5}},
    )

    precio: float = Field(ge=0.5, le=5, multiple_of=0.5, description="Puntuación de 0.5 a 5 (media estrella) por el precio.")
    calidad: float = Field(ge=0.5, le=5, multiple_of=0.5, description="Puntuación de 0.5 a 5 por la calidad del trabajo.")
    atencion: float = Field(ge=0.5, le=5, multiple_of=0.5, description="Puntuación de 0.5 a 5 por el trato al cliente.")
    puntualidad: float = Field(ge=0.5, le=5, multiple_of=0.5, description="Puntuación de 0.5 a 5 por el cumplimiento de horarios.")

    def promedio(self) -> float:
        valores = [self.precio, self.calidad, self.atencion, self.puntualidad]
        return round(sum(valores) / len(valores), 2)


class CalificacionesComentariosIn(BaseModel):
    """Lo que carga el cliente. La puntuación global no viaja en el request: la
    calcula el backend como promedio de los cuatro criterios."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "criterios": {"precio": 4, "calidad": 5, "atencion": 4.5, "puntualidad": 4.5},
                "comentario": "Excelente trabajo, muy prolijo y llegó puntual.",
            }
        }
    )

    criterios: CriteriosValoracion
    comentario: str | None = Field(default=None, max_length=200, description="Comentario de texto libre, opcional (máx. 200 caracteres).")

    def a_json(self) -> dict:
        """Arma el contenido que se guarda en la columna JSON de la reseña."""
        return {
            "puntuacion_global": self.criterios.promedio(),
            "criterios": self.criterios.model_dump(),
            "comentario": self.comentario,
        }


class SolicitudResenaCreate(BaseModel):
    """Modal "Datos del Cliente" del perfil público. El nombre es obligatorio y
    hay que cargar **al menos uno** de los dos datos de contacto; se pueden
    cargar los dos y entonces se usan los dos canales."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "nombre_cliente": "Juan Cliente",
                "telefono_cliente": "351-6924551",
                "email_cliente": "juan.cliente@example.com",
            }
        }
    )

    nombre_cliente: str = Field(min_length=2, max_length=100, description="Nombre del cliente. Obligatorio.")
    telefono_cliente: str | None = Field(
        default=None,
        description="10 dígitos: 3 o 4 de código de área + 7 o 6 de línea. Se acepta el guión (`351-6924551`). Sin 0, sin 15 y sin +54.",
    )
    email_cliente: EmailStr | None = Field(default=None, description="Correo del cliente, con validación estándar de email.")

    @field_validator("telefono_cliente")
    @classmethod
    def validar_telefono(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        value = value.strip()
        if not telefono_es_valido(value):
            raise ValueError(
                "Teléfono inválido: se esperan 10 dígitos (código de área + línea), con guión opcional, sin 0, sin 15 y sin +54"
            )
        return normalizar_telefono(value)

    @model_validator(mode="after")
    def exigir_un_contacto(self):
        if not self.telefono_cliente and not self.email_cliente:
            raise ValueError("Hay que cargar al menos un dato de contacto: teléfono o correo electrónico")
        return self


class SolicitudResenaOut(BaseModel):
    """Respuesta de la generación del enlace. Según qué contacto se cargó, trae
    la `whatsapp_url` armada, el correo ya enviado, o las dos cosas."""

    model_config = ConfigDict(from_attributes=True)

    id_solicitud: int
    oferente_id: int
    codigo_unico: str = Field(description="Código único que identifica el enlace de reseña.")
    origen: str = Field(description="WhatsApp | Email | Ambos — canal por el que se envía el enlace.")
    nombre_cliente: str
    telefono_cliente: str | None = None
    email_cliente: str | None = None
    estado: str = Field(description="Pendiente_Uso | Utilizada | Expirada")
    fecha_generacion: datetime
    fecha_expiracion: datetime

    url_resena: str = Field(description="Link del formulario de reseña, para compartir.")
    whatsapp_url: str | None = Field(
        default=None,
        description="Chat de WhatsApp con el mensaje precargado. Solo viene si se cargó teléfono. El envío lo dispara el usuario.",
    )
    email_enviado: bool = Field(description="true si se mandó el correo con el enlace.")


class SolicitudResenaVistaOut(BaseModel):
    """Alimenta el "Formulario de Reseña del Servicio": datos precargados y
    bloqueados, más el estado del enlace."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "codigo_unico": "a1b2c3d4e5f6",
                "oferente_id": 1,
                "nombre_oferente": "María Gómez",
                "nombre_cliente": "Juan Cliente",
                "telefono_cliente": "3516924551",
                "email_cliente": None,
                "estado": "Pendiente_Uso",
                "vencida": False,
                "utilizable": True,
                "fecha_expiracion": "2026-09-22T10:00:00Z",
            }
        }
    )

    codigo_unico: str
    oferente_id: int
    nombre_oferente: str = Field(description="Nombre y apellido del Profesional que se va a calificar.")
    nombre_cliente: str
    telefono_cliente: str | None = None
    email_cliente: str | None = Field(default=None, description="Viene vacío el dato de contacto que no se haya cargado.")
    estado: str = Field(description="Pendiente_Uso | Utilizada | Expirada")
    vencida: bool = Field(description="true si pasaron más de los días de validez desde la generación.")
    utilizable: bool = Field(description="true solo si el enlace sigue sin usar y no venció: la vista habilita la carga.")
    fecha_generacion: datetime
    fecha_expiracion: datetime


class ResenaCreate(BaseModel):
    """Los datos del cliente ya no viajan en el body: salen de la solicitud."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "codigo_unico": "a1b2c3d4e5f6",
                "calificaciones_comentarios": {
                    "criterios": {"precio": 4, "calidad": 5, "atencion": 4.5, "puntualidad": 4.5},
                    "comentario": "Excelente trabajo, muy prolijo y llegó puntual.",
                },
            }
        }
    )

    codigo_unico: str = Field(description="Código del enlace de reseña.")
    calificaciones_comentarios: CalificacionesComentariosIn


class ResenaModeracion(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {"aceptar": True}})

    aceptar: bool = Field(description="true = aceptar y publicar la reseña; false = rechazarla.")


class ResenaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_resena: int
    oferente_id: int
    solicitud_id: int
    nombre_cliente: str
    calificaciones_comentarios: dict
    estado: str = Field(description="Pendiente_Aceptacion | Aceptada | Rechazada")
    fecha_creacion: datetime


class ResenaPrivadaOut(ResenaOut):
    """Lo que ve el Profesional dueño de la reseña. A diferencia de la salida
    pública, expone el contacto del cliente: es una decisión explícita del
    equipo, para que pueda verificar la identidad y comunicarse."""

    telefono_cliente: str | None = None
    email_cliente: str | None = None


class ResenaAdminOut(ResenaOut):
    contacto_cliente_ingresado: str

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CriteriosValoracion(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"precio": 4, "calidad": 5, "atencion": 5, "puntualidad": 4}},
    )

    precio: int = Field(ge=1, le=5, description="Puntuación 1-5 por el precio del servicio.")
    calidad: int = Field(ge=1, le=5, description="Puntuación 1-5 por la calidad/ejecución del trabajo.")
    atencion: int = Field(ge=1, le=5, description="Puntuación 1-5 por el trato/atención al cliente.")
    puntualidad: int = Field(ge=1, le=5, description="Puntuación 1-5 por la puntualidad/cumplimiento de horarios.")


class CalificacionesComentariosIn(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "puntuacion_global": 5,
                "criterios": {"precio": 4, "calidad": 5, "atencion": 5, "puntualidad": 4},
                "comentario": "Excelente trabajo, muy prolijo y llegó puntual.",
            }
        }
    )

    puntuacion_global: int = Field(ge=1, le=5, description="Puntuación global de la reseña, 1 a 5.")
    criterios: CriteriosValoracion
    comentario: str | None = Field(default=None, max_length=1000, description="Comentario de texto libre, opcional.")


class SolicitudResenaCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"contacto_referencia_cliente": "Juan Cliente - +54 9 11 5555-1234"}}
    )

    contacto_referencia_cliente: str = Field(
        min_length=3,
        max_length=100,
        description="Contacto (nombre y WhatsApp o email) del cliente al que se le va a enviar el enlace de reseña.",
    )


class SolicitudResenaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_solicitud: int
    oferente_id: int
    codigo_unico: str = Field(description="Código único a incluir en el link/QR que se comparte con el cliente.")
    contacto_referencia_cliente: str
    estado: str = Field(description="Pendiente_Uso | Utilizada | Expirada")
    fecha_generacion: datetime
    fecha_expiracion: datetime | None = None


class ResenaCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "codigo_unico": "a1b2c3d4e5f6...",
                "nombre_cliente": "Juan Cliente",
                "contacto_cliente_ingresado": "juan.cliente@example.com",
                "calificaciones_comentarios": {
                    "puntuacion_global": 5,
                    "criterios": {"precio": 4, "calidad": 5, "atencion": 5, "puntualidad": 4},
                    "comentario": "Excelente trabajo, muy prolijo y llegó puntual.",
                },
            }
        }
    )

    codigo_unico: str = Field(description="Código recibido en el enlace/QR generado por el Oferente.")
    nombre_cliente: str = Field(min_length=2, max_length=100)
    contacto_cliente_ingresado: str = Field(min_length=3, max_length=100, description="WhatsApp o email del cliente que deja la reseña.")
    calificaciones_comentarios: CalificacionesComentariosIn


class ResenaModeracion(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {"aprobar": True}})

    aprobar: bool = Field(description="true = aprobar y publicar la reseña; false = rechazarla.")


class ResenaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_resena: int
    oferente_id: int
    solicitud_id: int
    nombre_cliente: str
    calificaciones_comentarios: dict
    estado: str = Field(description="Pendiente_Aprobacion | Aprobada | Rechazada")
    fecha_creacion: datetime


class ResenaAdminOut(ResenaOut):
    contacto_cliente_ingresado: str

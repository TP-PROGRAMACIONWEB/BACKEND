from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


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
    comentario: str | None = Field(default=None, max_length=1000, description="Comentario de texto libre, opcional.")

    def a_json(self) -> dict:
        """Arma el contenido que se guarda en la columna JSON de la reseña."""
        return {
            "puntuacion_global": self.criterios.promedio(),
            "criterios": self.criterios.model_dump(),
            "comentario": self.comentario,
        }


class SolicitudResenaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_solicitud: int
    oferente_id: int
    codigo_unico: str = Field(description="Código único que identifica el enlace de reseña.")
    origen: str = Field(description="Cliente_Email | Oferente_WhatsApp")
    nombre_cliente: str | None = Field(default=None, description="Solo viene cargado si el enlace lo pidió el cliente por correo.")
    email_cliente: str | None = None
    estado: str = Field(description="Pendiente_Uso | Utilizada | Expirada")
    fecha_generacion: datetime
    fecha_expiracion: datetime | None = None


class ResenaCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "codigo_unico": "a1b2c3d4e5f6",
                "nombre_cliente": "Juan Cliente",
                "contacto_cliente_ingresado": "juan.cliente@example.com",
                "calificaciones_comentarios": {
                    "criterios": {"precio": 4, "calidad": 5, "atencion": 4.5, "puntualidad": 4.5},
                    "comentario": "Excelente trabajo, muy prolijo y llegó puntual.",
                },
            }
        }
    )

    codigo_unico: str = Field(description="Código del enlace de reseña.")
    nombre_cliente: str = Field(min_length=2, max_length=100)
    contacto_cliente_ingresado: str = Field(min_length=3, max_length=100, description="Mail del cliente que deja la reseña.")
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
    estado: str = Field(description="Pendiente_Verificacion | Pendiente_Aprobacion | Aprobada | Rechazada")
    fecha_creacion: datetime


class ResenaAdminOut(ResenaOut):
    contacto_cliente_ingresado: str

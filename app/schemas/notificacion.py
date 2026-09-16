from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NotificacionOut(BaseModel):
    """Una tarjeta de la bandeja.

    Para las de `Resena_Nueva` trae **los datos de contacto del cliente y la
    fecha**, que es con lo que el Profesional verifica la identidad antes de
    decidir. Nunca trae el contenido de la reseña: ni la puntuación ni el
    comentario, que recién se publican si la acepta.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id_notificacion": 1,
                "tipo": "Resena_Nueva",
                "mensaje": "Juan Cliente (3516924551 / juan@example.com) dejó una reseña sobre tu trabajo. "
                "Revisá los datos de contacto y decidí si la aceptás.",
                "requiere_accion": True,
                "estado": "Pendiente",
                "resena_id": 7,
                "nombre_cliente": "Juan Cliente",
                "telefono_cliente": "3516924551",
                "email_cliente": "juan@example.com",
                "fecha_creacion": "2026-09-15T14:32:00Z",
                "fecha_resolucion": None,
            }
        },
    )

    id_notificacion: int
    tipo: str = Field(description="Resena_Nueva | Matricula_* — discrimina el origen de la notificación.")
    mensaje: str
    requiere_accion: bool = Field(description="true si espera Aceptar/Rechazar; false si es informativa y solo se marca leída.")
    estado: str = Field(description="Pendiente | Aceptada | Rechazada | Leida")
    resena_id: int | None = None

    nombre_cliente: str | None = Field(default=None, description="Solo en las notificaciones de reseña.")
    telefono_cliente: str | None = None
    email_cliente: str | None = None

    validacion_matricula_id: int | None = Field(default=None, description="Solo en las notificaciones de matrícula.")
    oferente_nombre: str | None = Field(default=None, description="Nombre del Profesional. Solo en las de reemplazo de matrícula.")
    tipo_profesional: str | None = None
    numero_matricula_actual: str | None = Field(default=None, description="Matrícula vigente antes del reemplazo pedido.")
    numero_matricula_solicitada: str | None = Field(default=None, description="Matrícula nueva que espera autorización.")

    fecha_creacion: datetime = Field(
        description="Fecha del hecho notificado. Para una reseña, cuándo la cargó el cliente, no cuándo se moderó."
    )
    fecha_resolucion: datetime | None = None


class ContadorNotificacionesOut(BaseModel):
    """Alimenta el badge de la campana.

    Se devuelven los dos números porque los documentos no coinciden: los casos
    de prueba hablan de "las notificaciones pendientes de rechazo/aceptación",
    pero las informativas de matrícula también quedan guardadas hasta abrirse
    (pregunta abierta #3 del plan). Con las dos cifras, el frontend puede
    mostrar una u otra sin tocar el backend cuando se defina.
    """

    model_config = ConfigDict(json_schema_extra={"example": {"pendientes_de_accion": 2, "sin_leer": 5}})

    pendientes_de_accion: int = Field(description="Pendientes que esperan una decisión. Es el contador que define el DER.")
    sin_leer: int = Field(description="Todas las pendientes, incluidas las informativas que todavía no se abrieron.")

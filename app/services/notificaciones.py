"""Creación y resolución de las notificaciones de la bandeja (la campana).

Vive fuera de los routers porque la escriben dos flujos distintos: la carga de
una reseña (HU-01) y, en la Fase 4, los resultados de la validación de matrícula
(HU-02). El estado de la notificación y el del hecho que la originó se mueven
siempre en la misma transacción: estas funciones agregan a la sesión y hacen
`flush`, nunca `commit`.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.notificacion import EstadoNotificacion, Notificacion, TipoNotificacion
from app.models.resena import Resena
from app.models.solicitud_resena import SolicitudResena


def _contacto_legible(solicitud: SolicitudResena) -> str:
    """Los dos datos si se cargaron los dos: el Profesional los usa para
    verificar la identidad del cliente antes de aceptar."""
    datos = [dato for dato in (solicitud.telefono_cliente, solicitud.email_cliente) if dato]
    return " / ".join(datos)


def crear_notificacion_resena_nueva(db: Session, resena: Resena, solicitud: SolicitudResena) -> Notificacion:
    """Avisa al Profesional que tiene una reseña esperando su decisión.

    El mensaje lleva **los datos de contacto y nada del contenido** de la
    reseña: el Profesional decide mirando quién la dejó, no qué dice.
    La fecha es la de creación de la reseña por el cliente, no la de la
    moderación (requisito explícito de los casos de prueba de QA).
    """
    notificacion = Notificacion(
        usuario_id=resena.oferente_id,
        tipo=TipoNotificacion.RESENA_NUEVA,
        mensaje=(
            f"{solicitud.nombre_cliente} ({_contacto_legible(solicitud)}) dejó una reseña sobre tu trabajo. "
            "Revisá los datos de contacto y decidí si la aceptás."
        ),
        requiere_accion=True,
        estado=EstadoNotificacion.PENDIENTE,
        resena_id=resena.id_resena,
        fecha_creacion=resena.fecha_creacion,
    )
    db.add(notificacion)
    db.flush()
    return notificacion


def resolver_notificacion_de_resena(db: Session, resena: Resena, aceptada: bool) -> Notificacion | None:
    """Cierra la notificación de la bandeja junto con la moderación de la reseña.

    Devuelve `None` si la reseña no tiene notificación asociada (reseñas
    cargadas antes de que existiera la bandeja, o datos de seed viejos): la
    moderación no se bloquea por eso.
    """
    notificacion = (
        db.query(Notificacion)
        .filter(
            Notificacion.resena_id == resena.id_resena,
            Notificacion.tipo == TipoNotificacion.RESENA_NUEVA,
            Notificacion.estado == EstadoNotificacion.PENDIENTE,
        )
        .first()
    )
    if not notificacion:
        return None

    notificacion.estado = EstadoNotificacion.ACEPTADA if aceptada else EstadoNotificacion.RECHAZADA
    notificacion.fecha_resolucion = datetime.now(timezone.utc)
    db.flush()
    return notificacion

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.database import get_db
from app.models.notificacion import EstadoNotificacion, Notificacion
from app.models.resena import Resena
from app.models.solicitud_resena import SolicitudResena
from app.models.usuario import Usuario
from app.schemas.notificacion import ContadorNotificacionesOut, NotificacionOut

router = APIRouter(prefix="/api/v1/notificaciones", tags=["Notificaciones"])

RESPUESTAS_AUTENTICADAS = {401: {"description": "Falta token o es inválido"}}


def _armar_salida(db: Session, notificacion: Notificacion) -> NotificacionOut:
    """Completa la tarjeta con los datos de contacto del cliente, que viven en
    la solicitud. El contenido de la reseña nunca se toca."""
    solicitud = None
    if notificacion.resena_id:
        resena = db.get(Resena, notificacion.resena_id)
        if resena:
            solicitud = db.get(SolicitudResena, resena.solicitud_id)

    return NotificacionOut(
        id_notificacion=notificacion.id_notificacion,
        tipo=notificacion.tipo,
        mensaje=notificacion.mensaje,
        requiere_accion=notificacion.requiere_accion,
        estado=notificacion.estado,
        resena_id=notificacion.resena_id,
        nombre_cliente=solicitud.nombre_cliente if solicitud else None,
        telefono_cliente=solicitud.telefono_cliente if solicitud else None,
        email_cliente=solicitud.email_cliente if solicitud else None,
        fecha_creacion=notificacion.fecha_creacion,
        fecha_resolucion=notificacion.fecha_resolucion,
    )


@router.get(
    "",
    response_model=list[NotificacionOut],
    summary="Bandeja de notificaciones del usuario autenticado",
    responses=RESPUESTAS_AUTENTICADAS,
)
def listar_notificaciones(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """HU-01 / CA04 — Lo que se despliega al abrir la campana, **más recientes
    primero**. Cada tarjeta de reseña muestra los datos de contacto que cargó el
    cliente y la fecha, para que el Profesional pueda verificar la identidad y
    comunicarse. Sirve tanto al Oferente como al Administrador: la bandeja es
    del usuario, no del perfil."""
    notificaciones = (
        db.query(Notificacion)
        .filter(Notificacion.usuario_id == usuario.id_usuario)
        .order_by(Notificacion.fecha_creacion.desc(), Notificacion.id_notificacion.desc())
        .all()
    )
    return [_armar_salida(db, notificacion) for notificacion in notificaciones]


@router.get(
    "/contador",
    response_model=ContadorNotificacionesOut,
    summary="Cantidad de notificaciones pendientes, para el badge de la campana",
    responses=RESPUESTAS_AUTENTICADAS,
)
def contar_notificaciones(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Solo cuenta las del usuario autenticado. Devuelve las dos cifras
    (pendientes de decisión y total sin leer) mientras siga abierta la
    pregunta #3 del plan sobre qué número muestra el badge."""
    pendientes = db.query(Notificacion).filter(
        Notificacion.usuario_id == usuario.id_usuario,
        Notificacion.estado == EstadoNotificacion.PENDIENTE,
    )
    sin_leer = pendientes.count()
    de_accion = pendientes.filter(Notificacion.requiere_accion.is_(True)).count()
    return ContadorNotificacionesOut(pendientes_de_accion=de_accion, sin_leer=sin_leer)


@router.patch(
    "/{notificacion_id}/leer",
    response_model=NotificacionOut,
    summary="Marcar como leída una notificación informativa",
    responses={
        **RESPUESTAS_AUTENTICADAS,
        400: {"description": "La notificación espera Aceptar/Rechazar, o ya se cerró"},
        403: {"description": "La notificación es de otro usuario"},
        404: {"description": "Notificación no encontrada"},
    },
)
def marcar_leida(
    notificacion_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Cierre de las informativas (los resultados de validación de matrícula),
    que quedan guardadas en la campana hasta que el Profesional las abre. Las
    que esperan una decisión no se cierran por acá: se resuelven aceptando o
    rechazando la reseña."""
    notificacion = db.get(Notificacion, notificacion_id)
    if not notificacion:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notificación no encontrada")
    if notificacion.usuario_id != usuario.id_usuario:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado")

    if notificacion.requiere_accion:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La notificación espera una decisión: se resuelve aceptando o rechazando la reseña",
        )
    if notificacion.estado != EstadoNotificacion.PENDIENTE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La notificación ya fue leída")

    notificacion.estado = EstadoNotificacion.LEIDA
    notificacion.fecha_resolucion = datetime.now(timezone.utc)
    db.commit()
    db.refresh(notificacion)
    return _armar_salida(db, notificacion)

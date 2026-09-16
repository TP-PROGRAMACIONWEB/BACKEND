import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user
from app.db.database import get_db
from app.models.alerta_admin import AlertaAdministrador
from app.models.oferente import Oferente
from app.models.resena import EstadoResena, Resena
from app.models.solicitud_resena import EstadoSolicitud, OrigenSolicitud, SolicitudResena
from app.models.usuario import Usuario
from app.schemas.resena import (
    ResenaCreate,
    ResenaModeracion,
    ResenaOut,
    ResenaPrivadaOut,
    SolicitudResenaCreate,
    SolicitudResenaOut,
    SolicitudResenaVistaOut,
)
from app.services.email import EmailError, EmailService, get_email_service, url_resena
from app.services.mensajes import armar_whatsapp_url
from app.services.notificaciones import crear_notificacion_resena_nueva, resolver_notificacion_de_resena
from app.services.resenas import recalcular_promedio

router = APIRouter(prefix="/api/v1", tags=["Reseñas"])

UMBRAL_RECHAZOS_ALERTA = 5
VENTANA_ULTIMAS_RESENAS = 10


def _verificar_propietario(oferente: Oferente, usuario: Usuario):
    if oferente.id_oferente != usuario.id_usuario:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado")


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _como_aware(momento: datetime) -> datetime:
    """SQLite devuelve los DateTime sin tzinfo; se los asume en UTC para poder
    compararlos con `_ahora()` sin romper en Postgres, que sí los trae aware."""
    return momento if momento.tzinfo else momento.replace(tzinfo=timezone.utc)


def _esta_vencida(solicitud: SolicitudResena) -> bool:
    return _como_aware(solicitud.fecha_expiracion) <= _ahora()


def _nombre_completo(oferente: Oferente) -> str:
    return f"{oferente.nombre} {oferente.apellido}"


def _salida_privada(resena: Resena, solicitud: SolicitudResena) -> ResenaPrivadaOut:
    """Salida para el Profesional dueño: incluye el contacto del cliente."""
    return ResenaPrivadaOut(
        id_resena=resena.id_resena,
        oferente_id=resena.oferente_id,
        solicitud_id=resena.solicitud_id,
        nombre_cliente=resena.nombre_cliente,
        calificaciones_comentarios=resena.calificaciones_comentarios,
        estado=resena.estado,
        fecha_creacion=resena.fecha_creacion,
        telefono_cliente=solicitud.telefono_cliente,
        email_cliente=solicitud.email_cliente,
    )


@router.post(
    "/oferentes/{oferente_id}/solicitudes-resena",
    response_model=SolicitudResenaOut,
    status_code=status.HTTP_201_CREATED,
    summary="Generar el enlace de reseña desde el perfil público (HU-01, sin login)",
    responses={
        404: {"description": "Oferente no encontrado"},
        422: {"description": "Falta el nombre, no se cargó ningún contacto, o el teléfono tiene formato inválido"},
        502: {"description": "No se pudo enviar el correo con el enlace"},
    },
)
def generar_solicitud_resena(
    oferente_id: int,
    payload: SolicitudResenaCreate,
    db: Session = Depends(get_db),
    email_service: EmailService = Depends(get_email_service),
):
    """RF10 / HU-01 — Cualquiera que esté en el perfil público presiona
    "Calificar", carga los **Datos del Cliente** y genera el enlace. No hace
    falta estar logueado: el botón lo ve tanto un cliente como el propio
    Profesional.

    El canal lo define el dato cargado:

    - **teléfono** → se devuelve la `whatsapp_url` con el mensaje precargado;
      el envío lo dispara una persona presionando "enviar" en WhatsApp;
    - **correo** → se manda el mail con el mismo texto;
    - **los dos** → se hacen las dos cosas.
    """
    oferente = db.get(Oferente, oferente_id)
    if not oferente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Oferente no encontrado")

    codigo = uuid.uuid4().hex
    solicitud = SolicitudResena(
        oferente_id=oferente_id,
        codigo_unico=codigo,
        nombre_cliente=payload.nombre_cliente,
        telefono_cliente=payload.telefono_cliente,
        email_cliente=payload.email_cliente,
        origen=OrigenSolicitud.desde_contacto(payload.telefono_cliente, payload.email_cliente),
        fecha_expiracion=_ahora() + timedelta(days=settings.solicitud_resena_dias_validez),
    )
    db.add(solicitud)
    db.flush()

    link = url_resena(codigo)
    nombre_oferente = _nombre_completo(oferente)

    # El correo es síncrono y crítico: si Brevo falla, no se crea la solicitud.
    email_enviado = False
    if payload.email_cliente:
        try:
            email_service.enviar_link_resena(
                email_cliente=payload.email_cliente,
                nombre_cliente=payload.nombre_cliente,
                nombre_oferente=nombre_oferente,
                codigo_unico=codigo,
            )
        except EmailError as exc:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
        email_enviado = True

    whatsapp = armar_whatsapp_url(payload.telefono_cliente, nombre_oferente, link) if payload.telefono_cliente else None

    db.commit()
    db.refresh(solicitud)
    return SolicitudResenaOut(
        id_solicitud=solicitud.id_solicitud,
        oferente_id=solicitud.oferente_id,
        codigo_unico=solicitud.codigo_unico,
        origen=solicitud.origen,
        nombre_cliente=solicitud.nombre_cliente,
        telefono_cliente=solicitud.telefono_cliente,
        email_cliente=solicitud.email_cliente,
        estado=solicitud.estado,
        fecha_generacion=solicitud.fecha_generacion,
        fecha_expiracion=solicitud.fecha_expiracion,
        url_resena=link,
        whatsapp_url=whatsapp,
        email_enviado=email_enviado,
    )


@router.get(
    "/solicitudes-resena/{codigo_unico}",
    response_model=SolicitudResenaVistaOut,
    summary="Datos precargados del formulario de reseña (público)",
    responses={404: {"description": "El código no existe"}},
)
def ver_solicitud_resena(codigo_unico: str, db: Session = Depends(get_db)):
    """HU-01 — Alimenta el "Formulario de Reseña del Servicio": el cliente ve su
    nombre y sus datos de contacto **precargados y bloqueados**, y la vista sabe
    si el enlace todavía se puede usar (un solo uso, 7 días de validez)."""
    solicitud = db.query(SolicitudResena).filter(SolicitudResena.codigo_unico == codigo_unico).first()
    if not solicitud:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enlace de reseña no encontrado")

    vencida = _esta_vencida(solicitud)
    # El estado Expirada se materializa recién cuando alguien abre el enlace;
    # no hay proceso que barra las solicitudes vencidas.
    if vencida and solicitud.estado == EstadoSolicitud.PENDIENTE_USO:
        solicitud.estado = EstadoSolicitud.EXPIRADA
        db.commit()
        db.refresh(solicitud)

    oferente = db.get(Oferente, solicitud.oferente_id)
    return SolicitudResenaVistaOut(
        codigo_unico=solicitud.codigo_unico,
        oferente_id=solicitud.oferente_id,
        nombre_oferente=_nombre_completo(oferente),
        nombre_cliente=solicitud.nombre_cliente,
        telefono_cliente=solicitud.telefono_cliente,
        email_cliente=solicitud.email_cliente,
        estado=solicitud.estado,
        vencida=vencida,
        utilizable=not vencida and solicitud.estado == EstadoSolicitud.PENDIENTE_USO,
        fecha_generacion=solicitud.fecha_generacion,
        fecha_expiracion=solicitud.fecha_expiracion,
    )


@router.post(
    "/resenas",
    response_model=ResenaOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar una reseña (público, sin login)",
    responses={
        400: {"description": "El enlace no existe, ya se usó o venció"},
        422: {"description": "Falta un criterio, está fuera de escala, o el comentario supera los 200 caracteres"},
    },
)
def registrar_resena(payload: ResenaCreate, db: Session = Depends(get_db)):
    """RF10 — El cliente deja la reseña accediendo con el `codigo_unico` del
    enlace, sin loguearse. Los datos del cliente **no viajan en el body**: se
    copian de la solicitud, que es donde quedaron registrados al generar el
    enlace. Queda en `Pendiente_Aceptacion` y, en la misma transacción, se crea
    la notificación en la bandeja del Profesional, que es donde la resuelve."""
    solicitud = db.query(SolicitudResena).filter(SolicitudResena.codigo_unico == payload.codigo_unico).first()
    if not solicitud or solicitud.estado != EstadoSolicitud.PENDIENTE_USO:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enlace de reseña inválido o ya utilizado")

    if _esta_vencida(solicitud):
        solicitud.estado = EstadoSolicitud.EXPIRADA
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El enlace de reseña venció")

    resena = Resena(
        oferente_id=solicitud.oferente_id,
        solicitud_id=solicitud.id_solicitud,
        nombre_cliente=solicitud.nombre_cliente,
        contacto_cliente_ingresado=solicitud.email_cliente or solicitud.telefono_cliente,
        calificaciones_comentarios=payload.calificaciones_comentarios.a_json(),
        estado=EstadoResena.PENDIENTE_ACEPTACION,
    )
    solicitud.estado = EstadoSolicitud.UTILIZADA
    db.add(resena)
    db.flush()
    # El refresh trae el id_resena y la fecha_creacion que pone la base: la
    # notificación tiene que mostrar esa fecha, la de la carga del cliente.
    db.refresh(resena)

    crear_notificacion_resena_nueva(db, resena, solicitud)

    db.commit()
    db.refresh(resena)
    return resena


@router.get(
    "/oferentes/{oferente_id}/resenas",
    response_model=list[ResenaOut],
    summary="Listar reseñas aceptadas de un oferente (público)",
)
def listar_resenas_publicas(oferente_id: int, db: Session = Depends(get_db)):
    """RF7 — Solo devuelve reseñas en estado `Aceptada`; las pendientes y
    rechazadas no son visibles públicamente ni suman al promedio."""
    return (
        db.query(Resena)
        .filter(Resena.oferente_id == oferente_id, Resena.estado == EstadoResena.ACEPTADA)
        .order_by(Resena.fecha_creacion.desc())
        .all()
    )


@router.patch(
    "/resenas/{resena_id}/moderar",
    response_model=ResenaPrivadaOut,
    summary="Aceptar o rechazar una reseña pendiente desde la bandeja",
    responses={
        400: {"description": "La reseña ya fue moderada (no está Pendiente_Aceptacion)"},
        401: {"description": "Falta token o es inválido"},
        403: {"description": "El oferente autenticado no es el dueño de la reseña"},
        404: {"description": "Reseña no encontrada"},
    },
)
def moderar_resena(
    resena_id: int,
    payload: ResenaModeracion,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """RF11/RF13 — El Profesional resuelve desde la campana la reseña que le
    llegó. Al **aceptar**, la reseña se publica en el perfil y se recalcula el
    promedio; al **rechazar**, no se publica ni suma al promedio. En las dos
    ramas se cierra la notificación asociada **en la misma transacción**.

    Si se rechazan 5 o más de las últimas 10 reseñas del oferente, se genera
    automáticamente una `AlertaAdministrador` (RF11) visible en
    `GET /admin/alertas`.

    La respuesta incluye el contacto del cliente: la ve solo el dueño."""
    resena = db.get(Resena, resena_id)
    if not resena:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reseña no encontrada")

    oferente = db.get(Oferente, resena.oferente_id)
    _verificar_propietario(oferente, usuario)

    if resena.estado != EstadoResena.PENDIENTE_ACEPTACION:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La reseña ya fue moderada")

    if payload.aceptar:
        resena.estado = EstadoResena.ACEPTADA
        db.flush()
        recalcular_promedio(db, oferente)
    else:
        resena.estado = EstadoResena.RECHAZADA
        db.flush()  # autoflush está desactivado; sin esto, la consulta de abajo no vería este rechazo

        ultimas = (
            db.query(Resena)
            .filter(Resena.oferente_id == oferente.id_oferente, Resena.estado != EstadoResena.PENDIENTE_ACEPTACION)
            .order_by(Resena.fecha_creacion.desc())
            .limit(VENTANA_ULTIMAS_RESENAS)
            .all()
        )
        rechazadas = sum(1 for r in ultimas if r.estado == EstadoResena.RECHAZADA)
        oferente.cantidad_rechazos_acumulados = rechazadas

        if rechazadas >= UMBRAL_RECHAZOS_ALERTA:
            alerta = AlertaAdministrador(
                oferente_id=oferente.id_oferente,
                motivo=f"{rechazadas} de las últimas {VENTANA_ULTIMAS_RESENAS} reseñas fueron rechazadas",
            )
            db.add(alerta)

    resolver_notificacion_de_resena(db, resena, aceptada=payload.aceptar)

    db.commit()
    db.refresh(resena)
    return _salida_privada(resena, db.get(SolicitudResena, resena.solicitud_id))

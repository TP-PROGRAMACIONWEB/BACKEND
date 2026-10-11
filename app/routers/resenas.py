import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user_opcional, get_oferente_registrado
from app.core.errores import error_negocio, error_validacion
from app.db.database import get_db
from app.models.alerta_admin import AlertaAdministrador, EstadoRevisionAlerta
from app.models.oferente import Oferente
from app.models.resena import EstadoResena, Resena
from app.models.solicitud_resena import EstadoSolicitud, OrigenSolicitud, SolicitudResena
from app.models.usuario import Usuario
from app.schemas.resena import (
    ResenaCreate,
    ResenaModeracion,
    ResenaOut,
    ResenaPrivadaOut,
    ResenaPublicaOut,
    SolicitudResenaCreate,
    SolicitudResenaOut,
    SolicitudResenaVistaOut,
)
from app.services.email import EmailError, EmailService, get_email_service, url_resena
from app.services.mensajes import armar_whatsapp_url, normalizar_telefono
from app.services.notificaciones import crear_notificacion_resena_nueva, resolver_notificacion_de_resena
from app.services.resenas import recalcular_promedio

router = APIRouter(prefix="/api/v1", tags=["Reseñas"])

UMBRAL_RECHAZOS_ALERTA = 5
VENTANA_ULTIMAS_RESENAS = 10
VENTANA_LIMITES_HORAS = 24


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _como_aware(momento: datetime) -> datetime:
    """SQLite devuelve los DateTime sin tzinfo; se los asume en UTC para poder
    compararlos con `_ahora()` sin romper en Postgres, que sí los trae aware."""
    return momento if momento.tzinfo else momento.replace(tzinfo=timezone.utc)


def _esta_vencida(solicitud: SolicitudResena) -> bool:
    return _como_aware(solicitud.fecha_expiracion) <= _ahora()


def _nombre_completo(oferente: Oferente) -> str:
    return oferente.nombre


def _nombre_publico(nombre: str) -> str:
    """Lo que ve el público de un cliente: el primer nombre y la inicial del
    segundo, si lo hay ("Juan Carlos Pérez" -> "Juan C."). Nunca el apellido."""
    partes = nombre.split()
    if not partes:
        return ""
    if len(partes) == 1:
        return partes[0]
    return f"{partes[0]} {partes[1][0].upper()}."


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


def _respuesta_solicitud(solicitud: SolicitudResena, oferente: Oferente, email_enviado: bool) -> SolicitudResenaOut:
    link = url_resena(solicitud.codigo_unico)
    whatsapp = (
        armar_whatsapp_url(solicitud.telefono_cliente, _nombre_completo(oferente), link) if solicitud.telefono_cliente else None
    )
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


def _validar_quien_genera(oferente: Oferente, es_dueno: bool, payload: SolicitudResenaCreate) -> None:
    """D8: sin login, el enlace solo se manda por correo y el correo es obligatorio.
    El Profesional dueño puede cargar teléfono, correo o los dos."""
    if es_dueno:
        if not payload.telefono_cliente and not payload.email_cliente:
            raise error_validacion(
                "telefono_cliente",
                "contacto_requerido",
                "Debe completar al menos un dato de contacto para poder generar el enlace.",
            )
        return
    if payload.telefono_cliente:
        raise error_validacion(
            "telefono_cliente",
            "telefono_no_permitido",
            "Para calificar sin iniciar sesión solo se pide el correo electrónico",
        )
    if not payload.email_cliente:
        raise error_validacion("email_cliente", "email_requerido", "Ingresá el correo electrónico del cliente")


def _validar_no_auto_resena(oferente: Oferente, payload: SolicitudResenaCreate) -> None:
    """El Profesional no puede calificarse a sí mismo con su propio contacto. No
    es infalible (puede usar otra casilla), pero cierra el caso trivial."""
    if payload.email_cliente and oferente.usuario and payload.email_cliente.lower() == oferente.usuario.email.lower():
        raise error_validacion("email_cliente", "contacto_propio", "No podés generar un enlace de reseña para vos mismo")
    if payload.telefono_cliente and normalizar_telefono(payload.telefono_cliente) == oferente.telefono:
        raise error_validacion("telefono_cliente", "contacto_propio", "No podés generar un enlace de reseña para vos mismo")


def _verificar_limites(db: Session, oferente_id: int, email_cliente: str | None) -> None:
    """Límites anti-spam: el endpoint es público y manda correos con la marca
    Offix. Se cuentan en la base porque en Vercel no hay memoria compartida."""
    desde = _ahora() - timedelta(hours=VENTANA_LIMITES_HORAS)
    if email_cliente:
        por_correo = (
            db.query(func.count(SolicitudResena.id_solicitud))
            .filter(SolicitudResena.email_cliente == email_cliente, SolicitudResena.fecha_generacion >= desde)
            .scalar()
        )
        if por_correo >= settings.resena_limite_por_email_24h:
            raise error_negocio(429, "limite_solicitudes", "Ya se enviaron demasiados enlaces a ese correo en las últimas 24 horas")

    por_oferente = (
        db.query(func.count(SolicitudResena.id_solicitud))
        .filter(SolicitudResena.oferente_id == oferente_id, SolicitudResena.fecha_generacion >= desde)
        .scalar()
    )
    if por_oferente >= settings.resena_limite_por_oferente_24h:
        raise error_negocio(429, "limite_solicitudes", "Este Profesional alcanzó el límite de enlaces de hoy")


def _solicitud_vigente_para_correo(db: Session, oferente_id: int, email_cliente: str) -> SolicitudResena | None:
    """Idempotencia: si ya hay un enlace sin usar y vigente para ese par
    (oferente, correo), se reenvía ese en vez de crear otro (también cubre el
    doble clic en "Generar enlace")."""
    candidatas = (
        db.query(SolicitudResena)
        .filter(
            SolicitudResena.oferente_id == oferente_id,
            SolicitudResena.email_cliente == email_cliente,
            SolicitudResena.estado == EstadoSolicitud.PENDIENTE_USO,
        )
        .order_by(SolicitudResena.id_solicitud.desc())
        .all()
    )
    return next((solicitud for solicitud in candidatas if not _esta_vencida(solicitud)), None)


@router.post(
    "/oferentes/{oferente_id}/solicitudes-resena",
    response_model=SolicitudResenaOut,
    status_code=status.HTTP_201_CREATED,
    summary="Generar el enlace de reseña desde el perfil público (HU-01)",
    responses={
        401: {"description": "Llegó un token inválido"},
        404: {"description": "Oferente no encontrado"},
        422: {
            "description": "Contacto que no corresponde a quien genera (`telefono_no_permitido`, `email_requerido`, "
            "`contacto_requerido`), o autocalificación (`contacto_propio`)"
        },
        429: {"description": "Superó el límite de enlaces por correo o por Profesional en 24 h (`limite_solicitudes`)"},
        502: {"description": "No se pudo enviar el correo con el enlace"},
    },
)
def generar_solicitud_resena(
    oferente_id: int,
    payload: SolicitudResenaCreate,
    db: Session = Depends(get_db),
    email_service: EmailService = Depends(get_email_service),
    usuario: Usuario | None = Depends(get_current_user_opcional),
):
    """RF10 / HU-01 — Cualquiera que esté en el perfil público presiona
    "Calificar" y carga los **Datos del Cliente**. No hace falta estar logueado.

    Qué contacto se acepta depende de quién lo pide (D8):

    - **anónimo u otro usuario** → solo correo, obligatorio;
    - **el Profesional dueño** → teléfono, correo o los dos. Con teléfono se
      devuelve la `whatsapp_url` con el mensaje precargado; con correo se manda
      el mail.
    """
    oferente = db.get(Oferente, oferente_id)
    if not oferente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Oferente no encontrado")

    es_dueno = usuario is not None and usuario.id_usuario == oferente.id_oferente
    _validar_quien_genera(oferente, es_dueno, payload)
    _validar_no_auto_resena(oferente, payload)

    if payload.email_cliente:
        existente = _solicitud_vigente_para_correo(db, oferente.id_oferente, payload.email_cliente)
        if existente:
            try:
                _enviar_correo(email_service, existente, oferente)
            except EmailError as exc:
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
            return _respuesta_solicitud(existente, oferente, email_enviado=True)

    _verificar_limites(db, oferente.id_oferente, payload.email_cliente)

    solicitud = SolicitudResena(
        oferente_id=oferente.id_oferente,
        codigo_unico=uuid.uuid4().hex,
        nombre_cliente=payload.nombre_cliente,
        telefono_cliente=payload.telefono_cliente,
        email_cliente=payload.email_cliente,
        origen=OrigenSolicitud.desde_contacto(payload.telefono_cliente, payload.email_cliente),
        fecha_expiracion=_ahora() + timedelta(days=settings.solicitud_resena_dias_validez),
    )
    db.add(solicitud)
    db.flush()

    # El correo es síncrono y crítico: si Brevo falla, no se crea la solicitud.
    email_enviado = False
    if payload.email_cliente:
        try:
            _enviar_correo(email_service, solicitud, oferente)
        except EmailError as exc:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
        email_enviado = True

    db.commit()
    db.refresh(solicitud)
    return _respuesta_solicitud(solicitud, oferente, email_enviado=email_enviado)


def _enviar_correo(email_service: EmailService, solicitud: SolicitudResena, oferente: Oferente) -> None:
    email_service.enviar_link_resena(
        email_cliente=solicitud.email_cliente,
        nombre_cliente=solicitud.nombre_cliente,
        nombre_oferente=_nombre_completo(oferente),
        codigo_unico=solicitud.codigo_unico,
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
        400: {"description": "El enlace no existe (`enlace_inexistente`), ya se usó (`enlace_utilizado`) o venció (`enlace_vencido`)"},
        422: {"description": "Falta un criterio, está fuera de escala, o el comentario supera los 200 caracteres"},
    },
)
def registrar_resena(payload: ResenaCreate, db: Session = Depends(get_db)):
    """RF10 — El cliente deja la reseña con el `codigo_unico` del enlace, sin
    loguearse. Los datos del cliente salen de la solicitud, no del body. Queda en
    `Pendiente_Aceptacion` y, en la misma transacción, se crea la notificación en
    la bandeja del Profesional.

    La solicitud pasa a `Utilizada` con un UPDATE condicional: si dos envíos
    llegan a la vez, solo uno gana y el otro recibe `enlace_utilizado`."""
    solicitud = db.query(SolicitudResena).filter(SolicitudResena.codigo_unico == payload.codigo_unico).first()
    if solicitud is None:
        raise error_negocio(status.HTTP_400_BAD_REQUEST, "enlace_inexistente", "El enlace de reseña no existe")
    if solicitud.estado == EstadoSolicitud.UTILIZADA:
        raise error_negocio(status.HTTP_400_BAD_REQUEST, "enlace_utilizado", "El enlace de reseña ya fue utilizado")
    if solicitud.estado == EstadoSolicitud.EXPIRADA or _esta_vencida(solicitud):
        if solicitud.estado == EstadoSolicitud.PENDIENTE_USO:
            solicitud.estado = EstadoSolicitud.EXPIRADA
            db.commit()
        raise error_negocio(status.HTTP_400_BAD_REQUEST, "enlace_vencido", "El enlace de reseña venció")

    reclamadas = db.execute(
        update(SolicitudResena)
        .where(SolicitudResena.id_solicitud == solicitud.id_solicitud, SolicitudResena.estado == EstadoSolicitud.PENDIENTE_USO)
        .values(estado=EstadoSolicitud.UTILIZADA)
        .execution_options(synchronize_session=False)
    ).rowcount
    if reclamadas == 0:
        db.rollback()
        raise error_negocio(status.HTTP_400_BAD_REQUEST, "enlace_utilizado", "El enlace de reseña ya fue utilizado")

    resena = Resena(
        oferente_id=solicitud.oferente_id,
        solicitud_id=solicitud.id_solicitud,
        nombre_cliente=solicitud.nombre_cliente,
        contacto_cliente_ingresado=solicitud.email_cliente or solicitud.telefono_cliente,
        calificaciones_comentarios=payload.calificaciones_comentarios.a_json(),
        estado=EstadoResena.PENDIENTE_ACEPTACION,
    )
    db.add(resena)
    try:
        db.flush()
    except IntegrityError as exc:
        # Segunda línea de defensa: UNIQUE(solicitud_id) en RESENAS.
        db.rollback()
        raise error_negocio(status.HTTP_400_BAD_REQUEST, "enlace_utilizado", "El enlace de reseña ya fue utilizado") from exc
    # El refresh trae el id_resena y la fecha_creacion que pone la base: la
    # notificación tiene que mostrar esa fecha, la de la carga del cliente.
    db.refresh(resena)

    crear_notificacion_resena_nueva(db, resena, solicitud)

    db.commit()
    db.refresh(resena)
    # Sin contacto: quien deja la reseña es anónimo y el dato no le corresponde.
    return resena


@router.get(
    "/oferentes/{oferente_id}/resenas",
    response_model=list[ResenaPublicaOut],
    summary="Opiniones aceptadas de un Profesional (público)",
)
def listar_resenas_publicas(oferente_id: int, db: Session = Depends(get_db)):
    """RF7 / HU-01 T07 — Solo reseñas `Aceptada`, más nuevas primero. Sin datos
    de contacto del cliente y con el nombre reducido a "Juan C."."""
    resenas = (
        db.query(Resena)
        .filter(Resena.oferente_id == oferente_id, Resena.estado == EstadoResena.ACEPTADA)
        .order_by(Resena.fecha_creacion.desc(), Resena.id_resena.desc())
        .all()
    )
    return [
        ResenaPublicaOut(
            id_resena=resena.id_resena,
            cliente=_nombre_publico(resena.nombre_cliente),
            puntuacion_global=resena.calificaciones_comentarios["puntuacion_global"],
            criterios=resena.calificaciones_comentarios["criterios"],
            comentario=resena.calificaciones_comentarios.get("comentario"),
            fecha_creacion=resena.fecha_creacion,
        )
        for resena in resenas
    ]


@router.patch(
    "/resenas/{resena_id}/moderar",
    response_model=ResenaPrivadaOut,
    summary="Aceptar o rechazar una reseña pendiente desde la bandeja",
    responses={
        400: {"description": "La reseña ya fue moderada (`resena_ya_moderada`)"},
        401: {"description": "Falta token o es inválido"},
        403: {"description": "El Profesional autenticado no es el dueño de la reseña, o falta completar el registro"},
        404: {"description": "Reseña no encontrada"},
    },
)
def moderar_resena(
    resena_id: int,
    payload: ResenaModeracion,
    db: Session = Depends(get_db),
    oferente: Oferente = Depends(get_oferente_registrado),
):
    """RF11/RF13 — El Profesional resuelve desde la campana la reseña que le
    llegó. Al **aceptar**, la reseña se publica y se recalcula el promedio; al
    **rechazar**, no se publica ni suma al promedio. En las dos ramas se cierra la
    notificación asociada **en la misma transacción**.

    Si se rechazan 5 o más de las últimas 10 reseñas, se genera una
    `AlertaAdministrador`. Mientras haya una alerta pendiente, no se crea otra.

    La respuesta incluye el contacto del cliente: la ve solo el dueño."""
    resena = db.get(Resena, resena_id)
    if not resena:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reseña no encontrada")
    if resena.oferente_id != oferente.id_oferente:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado")

    if resena.estado != EstadoResena.PENDIENTE_ACEPTACION:
        raise error_negocio(status.HTTP_400_BAD_REQUEST, "resena_ya_moderada", "La reseña ya fue moderada")

    if payload.aceptar:
        resena.estado = EstadoResena.ACEPTADA
        db.flush()
        recalcular_promedio(db, oferente)
    else:
        resena.estado = EstadoResena.RECHAZADA
        db.flush()  # sin esto, la consulta de abajo no vería este rechazo

        ultimas = (
            db.query(Resena)
            .filter(Resena.oferente_id == oferente.id_oferente, Resena.estado != EstadoResena.PENDIENTE_ACEPTACION)
            .order_by(Resena.fecha_creacion.desc())
            .limit(VENTANA_ULTIMAS_RESENAS)
            .all()
        )
        rechazadas = sum(1 for r in ultimas if r.estado == EstadoResena.RECHAZADA)
        oferente.cantidad_rechazos_acumulados = rechazadas

        alerta_pendiente = (
            db.query(AlertaAdministrador.id_alerta)
            .filter(
                AlertaAdministrador.oferente_id == oferente.id_oferente,
                AlertaAdministrador.estado_revision == EstadoRevisionAlerta.PENDIENTE,
            )
            .first()
        )
        if rechazadas >= UMBRAL_RECHAZOS_ALERTA and alerta_pendiente is None:
            db.add(
                AlertaAdministrador(
                    oferente_id=oferente.id_oferente,
                    motivo=f"{rechazadas} de las últimas {VENTANA_ULTIMAS_RESENAS} reseñas fueron rechazadas",
                )
            )

    resolver_notificacion_de_resena(db, resena, aceptada=payload.aceptar)

    db.commit()
    db.refresh(resena)
    return _salida_privada(resena, db.get(SolicitudResena, resena.solicitud_id))

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.database import get_db
from app.models.alerta_admin import AlertaAdministrador
from app.models.oferente import Oferente
from app.models.resena import EstadoResena, Resena
from app.models.solicitud_resena import EstadoSolicitud, SolicitudResena
from app.models.usuario import Usuario
from app.schemas.resena import (
    ResenaCreate,
    ResenaModeracion,
    ResenaOut,
    SolicitudResenaCreate,
    SolicitudResenaOut,
)

router = APIRouter(prefix="/api/v1", tags=["Reseñas"])

UMBRAL_RECHAZOS_ALERTA = 5
VENTANA_ULTIMAS_RESENAS = 10


def _verificar_propietario(oferente: Oferente, usuario: Usuario):
    if oferente.id_oferente != usuario.id_usuario:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado")


@router.post(
    "/oferentes/{oferente_id}/solicitudes-resena",
    response_model=SolicitudResenaOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Reseñas"],
    summary="Generar enlace de reseña (paso 1 del flujo HU-01)",
    responses={
        401: {"description": "Falta token o es inválido"},
        403: {"description": "El oferente autenticado no es el dueño del perfil"},
        404: {"description": "Oferente no encontrado"},
        422: {"description": "Falta contacto_referencia_cliente o es inválido"},
    },
)
def generar_solicitud_resena(
    oferente_id: int,
    payload: SolicitudResenaCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """RF10 — El Oferente (logueado) genera el link/QR único de reseña, indicando
    el contacto de referencia del cliente al que se lo va a enviar.

    Sprint 1: el envío del enlace es **simulado** — no se manda mail/WhatsApp
    real todavía. El `codigo_unico` devuelto en la respuesta es el dato que hay
    que pegar en `POST /api/v1/resenas` (o codificar en un QR) para simular el
    link que recibiría el cliente."""
    oferente = db.get(Oferente, oferente_id)
    if not oferente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Oferente no encontrado")
    _verificar_propietario(oferente, usuario)

    solicitud = SolicitudResena(
        oferente_id=oferente_id,
        codigo_unico=uuid.uuid4().hex,
        contacto_referencia_cliente=payload.contacto_referencia_cliente,
    )
    db.add(solicitud)
    db.commit()
    db.refresh(solicitud)
    return solicitud


@router.post(
    "/resenas",
    response_model=ResenaOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar una reseña (paso 2 del flujo HU-01, público, sin login)",
    responses={
        400: {"description": "codigo_unico inexistente o ya utilizado"},
        422: {"description": "Falta un campo obligatorio o un criterio está fuera de 1-5"},
    },
)
def registrar_resena(payload: ResenaCreate, db: Session = Depends(get_db)):
    """RF10 — El cliente deja la reseña accediendo exclusivamente vía el
    `codigo_unico` recibido en el enlace/QR, sin necesidad de loguearse. Queda
    en estado `Pendiente_Aprobacion` hasta que el Oferente la modere
    (`PATCH /resenas/{id}/moderar`)."""
    solicitud = db.query(SolicitudResena).filter(SolicitudResena.codigo_unico == payload.codigo_unico).first()
    if not solicitud or solicitud.estado != EstadoSolicitud.PENDIENTE_USO:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enlace de reseña inválido o ya utilizado")

    resena = Resena(
        oferente_id=solicitud.oferente_id,
        solicitud_id=solicitud.id_solicitud,
        nombre_cliente=payload.nombre_cliente,
        contacto_cliente_ingresado=payload.contacto_cliente_ingresado,
        calificaciones_comentarios=payload.calificaciones_comentarios.model_dump(),
        estado=EstadoResena.PENDIENTE_APROBACION,
    )
    solicitud.estado = EstadoSolicitud.UTILIZADA
    db.add(resena)
    db.commit()
    db.refresh(resena)
    return resena


@router.get(
    "/oferentes/{oferente_id}/resenas",
    response_model=list[ResenaOut],
    summary="Listar reseñas aprobadas de un oferente (público)",
)
def listar_resenas_publicas(oferente_id: int, db: Session = Depends(get_db)):
    """RF7 — Solo devuelve reseñas en estado `Aprobada`; las pendientes y
    rechazadas no son visibles públicamente."""
    return (
        db.query(Resena)
        .filter(Resena.oferente_id == oferente_id, Resena.estado == EstadoResena.APROBADA)
        .order_by(Resena.fecha_creacion.desc())
        .all()
    )


@router.patch(
    "/resenas/{resena_id}/moderar",
    response_model=ResenaOut,
    summary="Aprobar o rechazar una reseña pendiente",
    responses={
        400: {"description": "La reseña ya fue moderada (no está Pendiente_Aprobacion)"},
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
    """RF11/RF13 — El Oferente aprueba o rechaza la reseña. Si se rechazan 5 o
    más de las últimas 10 reseñas del oferente, se genera automáticamente una
    `AlertaAdministrador` (RF11) visible en `GET /admin/alertas`."""
    resena = db.get(Resena, resena_id)
    if not resena:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reseña no encontrada")

    oferente = db.get(Oferente, resena.oferente_id)
    _verificar_propietario(oferente, usuario)

    if resena.estado != EstadoResena.PENDIENTE_APROBACION:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La reseña ya fue moderada")

    if payload.aprobar:
        resena.estado = EstadoResena.APROBADA
    else:
        resena.estado = EstadoResena.RECHAZADA
        db.flush()  # autoflush está desactivado; sin esto, la consulta de abajo no vería este rechazo

        ultimas = (
            db.query(Resena)
            .filter(Resena.oferente_id == oferente.id_oferente, Resena.estado != EstadoResena.PENDIENTE_APROBACION)
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

    db.commit()
    db.refresh(resena)
    return resena

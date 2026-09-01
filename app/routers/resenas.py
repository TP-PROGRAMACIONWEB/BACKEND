import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.database import get_db
from app.models.alerta_admin import AlertaAdministrador
from app.models.oferente import Oferente
from app.models.resena import Resena
from app.models.solicitud_resena import SolicitudResena
from app.models.usuario import Usuario
from app.schemas.resena import (
    ResenaCreate,
    ResenaModeracion,
    ResenaOut,
    SolicitudResenaOut,
)

router = APIRouter(prefix="/api/v1", tags=["Reseñas"])

UMBRAL_RECHAZOS_ALERTA = 5
VENTANA_ULTIMAS_RESENAS = 10


def _verificar_propietario(oferente: Oferente, usuario: Usuario):
    if oferente.id_usuario != usuario.id_usuario:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado")


@router.post(
    "/oferentes/{oferente_id}/solicitudes-resena",
    response_model=SolicitudResenaOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Reseñas"],
)
def generar_solicitud_resena(
    oferente_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """RF10 — El Oferente genera el link/QR único de reseña."""
    oferente = db.get(Oferente, oferente_id)
    if not oferente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Oferente no encontrado")
    _verificar_propietario(oferente, usuario)

    solicitud = SolicitudResena(oferente_id=oferente_id, codigo_unico=uuid.uuid4().hex)
    db.add(solicitud)
    db.commit()
    db.refresh(solicitud)
    return solicitud


@router.post("/resenas", response_model=ResenaOut, status_code=status.HTTP_201_CREATED)
def registrar_resena(payload: ResenaCreate, db: Session = Depends(get_db)):
    """RF10 — El cliente deja la reseña accediendo exclusivamente vía link único, sin login."""
    solicitud = db.query(SolicitudResena).filter(SolicitudResena.codigo_unico == payload.codigo_unico).first()
    if not solicitud or solicitud.estado != "pendiente":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enlace de reseña inválido o ya utilizado")

    resena = Resena(
        oferente_id=solicitud.oferente_id,
        solicitud_id=solicitud.id_solicitud,
        nombre_cliente=payload.nombre_cliente,
        contacto_cliente_ingresado=payload.contacto_cliente_ingresado,
        calificacion=payload.calificacion,
        comentario=payload.comentario,
        estado="pendiente",
    )
    solicitud.estado = "utilizada"
    db.add(resena)
    db.commit()
    db.refresh(resena)
    return resena


@router.get("/oferentes/{oferente_id}/resenas", response_model=list[ResenaOut])
def listar_resenas_publicas(oferente_id: int, db: Session = Depends(get_db)):
    """RF7 — Reseñas aprobadas visibles en el perfil público."""
    return (
        db.query(Resena)
        .filter(Resena.oferente_id == oferente_id, Resena.estado == "aprobada")
        .order_by(Resena.fecha_creacion.desc())
        .all()
    )


@router.patch("/resenas/{resena_id}/moderar", response_model=ResenaOut)
def moderar_resena(
    resena_id: int,
    payload: ResenaModeracion,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """RF11/RF13 — El Oferente aprueba o rechaza la reseña; controla alertas por rechazos reiterados."""
    resena = db.get(Resena, resena_id)
    if not resena:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reseña no encontrada")

    oferente = db.get(Oferente, resena.oferente_id)
    _verificar_propietario(oferente, usuario)

    if resena.estado != "pendiente":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La reseña ya fue moderada")

    if payload.aprobar:
        resena.estado = "aprobada"
    else:
        resena.estado = "rechazada"
        resena.replica_oferente = payload.replica_oferente

        ultimas = (
            db.query(Resena)
            .filter(Resena.oferente_id == oferente.id_oferente, Resena.estado != "pendiente")
            .order_by(Resena.fecha_creacion.desc())
            .limit(VENTANA_ULTIMAS_RESENAS)
            .all()
        )
        rechazadas = sum(1 for r in ultimas if r.estado == "rechazada")
        oferente.cantidad_resenas_rechazadas = rechazadas

        if rechazadas >= UMBRAL_RECHAZOS_ALERTA:
            alerta = AlertaAdministrador(
                oferente_id=oferente.id_oferente,
                motivo=f"{rechazadas} de las últimas {VENTANA_ULTIMAS_RESENAS} reseñas fueron rechazadas",
            )
            db.add(alerta)

    db.commit()
    db.refresh(resena)
    return resena

import enum

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import require_admin
from app.db.database import get_db
from app.models.alerta_admin import AlertaAdministrador
from app.models.oferente import EstadoVerificacion, Oferente
from app.models.resena import EstadoResena, Resena
from app.models.usuario import EstadoCuenta, Usuario
from app.schemas.oferente import OferenteOut
from app.schemas.resena import ResenaAdminOut
from app.schemas.usuario import UsuarioOut

RESPUESTAS_ADMIN_COMUNES = {
    401: {"description": "Falta token o es inválido"},
    403: {"description": "Requiere rol Administrador"},
}

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["Administración"],
    dependencies=[Depends(require_admin)],
    responses=RESPUESTAS_ADMIN_COMUNES,
)


class EstadoCuentaEnum(str, enum.Enum):
    ACTIVA = EstadoCuenta.ACTIVA
    SUSPENDIDA = EstadoCuenta.SUSPENDIDA
    BLOQUEADA = EstadoCuenta.BLOQUEADA


class EstadoVerificacionEnum(str, enum.Enum):
    PENDIENTE = EstadoVerificacion.PENDIENTE
    VERIFICADO = EstadoVerificacion.VERIFICADO
    RECHAZADO = EstadoVerificacion.RECHAZADO


@router.get("/usuarios", response_model=list[UsuarioOut], summary="Listar todos los usuarios")
def listar_usuarios(db: Session = Depends(get_db)):
    """RF14 — Gestión de usuarios."""
    return db.query(Usuario).all()


@router.patch(
    "/usuarios/{usuario_id}/estado",
    response_model=UsuarioOut,
    summary="Suspender/bloquear/reactivar un usuario",
    responses={404: {"description": "Usuario no encontrado"}},
)
def cambiar_estado_usuario(usuario_id: int, estado: EstadoCuentaEnum, db: Session = Depends(get_db)):
    """RF15 — Bloquear o suspender usuarios. Un usuario Suspendida/Bloqueada no puede hacer login."""
    usuario = db.get(Usuario, usuario_id)
    if not usuario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

    usuario.estado_cuenta = estado.value
    db.commit()
    db.refresh(usuario)
    return usuario


@router.patch(
    "/oferentes/{oferente_id}/verificacion",
    response_model=OferenteOut,
    summary="Marcar manualmente el estado de verificación de matrícula",
    responses={404: {"description": "Oferente no encontrado"}},
)
def actualizar_estado_verificacion(oferente_id: int, estado_verificacion: EstadoVerificacionEnum, db: Session = Depends(get_db)):
    """HU-02 T07 — Simula la integración con el ente validador de matrículas
    (electricista, gasista, plomero, técnico en aire acondicionado): para
    Sprint 1 el estado se marca manualmente en vez de consultar un servicio
    externo real."""
    oferente = db.get(Oferente, oferente_id)
    if not oferente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Oferente no encontrado")

    oferente.estado_verificacion = estado_verificacion.value
    db.commit()
    db.refresh(oferente)
    return oferente


@router.get("/alertas", summary="Listar alertas generadas por rechazos reiterados de reseñas")
def listar_alertas(db: Session = Depends(get_db)):
    """RF17 — Revisión de alertas por rechazos reiterados de reseñas."""
    return db.query(AlertaAdministrador).order_by(AlertaAdministrador.fecha_creacion.desc()).all()


@router.get(
    "/resenas/rechazadas",
    response_model=list[ResenaAdminOut],
    summary="Listar reseñas rechazadas por sus oferentes",
)
def listar_resenas_rechazadas(db: Session = Depends(get_db)):
    """RF17 — El administrador puede revisar y revertir rechazos incorrectos."""
    return db.query(Resena).filter(Resena.estado == EstadoResena.RECHAZADA).order_by(Resena.fecha_creacion.desc()).all()


@router.patch(
    "/resenas/{resena_id}/publicar",
    response_model=ResenaAdminOut,
    summary="Publicar una reseña que el oferente había rechazado",
    responses={404: {"description": "Reseña no encontrada"}},
)
def publicar_resena_rechazada(resena_id: int, db: Session = Depends(get_db)):
    """RF17 — El Administrador, como instancia final, publica una reseña rechazada por el Oferente."""
    resena = db.get(Resena, resena_id)
    if not resena:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reseña no encontrada")

    resena.estado = EstadoResena.ACEPTADA
    db.commit()
    db.refresh(resena)
    return resena

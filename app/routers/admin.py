import enum
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import require_admin
from app.db.database import get_db
from app.models.alerta_admin import AlertaAdministrador
from app.models.matricula import EstadoReemplazo, ResultadoValidacion, ValidacionMatricula
from app.models.notificacion import EstadoNotificacion, Notificacion
from app.models.oferente import EstadoVerificacion, Oferente
from app.models.resena import EstadoResena, Resena
from app.models.usuario import EstadoCuenta, Usuario
from app.schemas.matricula import ReemplazoResolucionIn, ReemplazoResueltoOut
from app.schemas.oferente import OferenteOut
from app.schemas.resena import ResenaAdminOut
from app.schemas.usuario import UsuarioOut
from app.services.matriculas import resolver_reemplazo
from app.services.resenas import recalcular_promedio

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
    db.flush()
    # Publicarla la hace visible en el perfil, así que también tiene que entrar
    # al promedio: el recálculo es el mismo que usa la moderación del Oferente.
    recalcular_promedio(db, db.get(Oferente, resena.oferente_id))
    db.commit()
    db.refresh(resena)
    return resena


@router.patch(
    "/matriculas/reemplazos/{id_validacion}",
    response_model=ReemplazoResueltoOut,
    summary="Autorizar o denegar un reemplazo de matrícula pedido por un Oferente",
    responses={
        400: {"description": "El reemplazo ya fue resuelto (o fue reemplazado por un pedido más nuevo)"},
        404: {"description": "No hay un pedido de reemplazo con ese id"},
    },
)
def resolver_reemplazo_matricula(id_validacion: int, payload: ReemplazoResolucionIn, db: Session = Depends(get_db)):
    """HU-02 — Mientras el Administrador no decide, sigue vigente la matrícula
    anterior: el reemplazo recién se aplica acá. En la misma transacción se
    cierra la notificación accionable del Administrador y se avisa al
    Oferente del resultado."""
    validacion = db.get(ValidacionMatricula, id_validacion)
    if not validacion or validacion.resultado != ResultadoValidacion.REEMPLAZO_SOLICITADO:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No hay un pedido de reemplazo con ese id")
    if validacion.estado_reemplazo == EstadoReemplazo.SUPERSEDED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El Oferente pidió un reemplazo más nuevo para este oficio: resolvé ese pedido",
        )
    if validacion.estado_reemplazo != EstadoReemplazo.PENDIENTE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El reemplazo ya fue resuelto")

    matricula = resolver_reemplazo(db, validacion, payload.autorizar)

    notificaciones_admin = (
        db.query(Notificacion)
        .filter(Notificacion.validacion_matricula_id == id_validacion, Notificacion.requiere_accion.is_(True))
        .all()
    )
    for notificacion in notificaciones_admin:
        notificacion.estado = EstadoNotificacion.ACEPTADA if payload.autorizar else EstadoNotificacion.RECHAZADA
        notificacion.fecha_resolucion = datetime.now(timezone.utc)

    db.commit()
    db.refresh(validacion)
    return ReemplazoResueltoOut(id_validacion=validacion.id_validacion, estado_reemplazo=validacion.estado_reemplazo, matricula=matricula)

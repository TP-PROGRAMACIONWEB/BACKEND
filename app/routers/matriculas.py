from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.database import get_db
from app.models.matricula import Matricula, ValidacionMatricula
from app.models.oferente import Oferente
from app.models.usuario import Usuario
from app.schemas.matricula import MatriculaOut, ValidacionHistorialOut, ValidacionMatriculaIn, ValidacionMatriculaOut
from app.services.matriculas import MENSAJES_RESULTADO, validar_matricula

router = APIRouter(prefix="/api/v1/oferentes/me/matriculas", tags=["Matrículas"])

RESPUESTAS_COMUNES = {
    401: {"description": "Falta token o es inválido"},
    404: {"description": "El usuario autenticado no tiene perfil de Oferente"},
}


def _oferente_actual(db: Session, usuario: Usuario) -> Oferente:
    oferente = db.get(Oferente, usuario.id_usuario)
    if not oferente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El usuario no tiene perfil de Oferente")
    return oferente


def _matricula_vigente(db: Session, oferente_id: int, tipo_profesional: str) -> Matricula | None:
    return (
        db.query(Matricula)
        .filter(Matricula.oferente_id == oferente_id, Matricula.tipo_profesional == tipo_profesional)
        .first()
    )


@router.post(
    "/validaciones",
    response_model=ValidacionMatriculaOut,
    summary="Validar (fidelizar) una matrícula profesional contra el padrón",
    responses={
        **RESPUESTAS_COMUNES,
        422: {"description": "Tipo inválido, o el número no tiene la cantidad de dígitos exigida"},
    },
)
def crear_validacion(
    payload: ValidacionMatriculaIn,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """HU-02 — El Profesional logueado carga tipo y número; la validación es
    **síncrona**, contra el padrón cargado en la base (con timeout de
    `settings.matricula_timeout_segundos`, simulado con la matrícula trampa).
    Devuelve un código de `resultado` con su mensaje; el frontend lo renderiza.
    """
    oferente = _oferente_actual(db, usuario)
    validacion = validar_matricula(db, oferente, payload.tipo_profesional, payload.numero_matricula)
    db.commit()

    matricula = _matricula_vigente(db, oferente.id_oferente, payload.tipo_profesional)
    return ValidacionMatriculaOut(resultado=validacion.resultado, mensaje=MENSAJES_RESULTADO[validacion.resultado], matricula=matricula)


@router.get(
    "",
    response_model=list[MatriculaOut],
    summary="Matrículas fidelizadas del Profesional autenticado",
    responses=RESPUESTAS_COMUNES,
)
def listar_matriculas(db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    oferente = _oferente_actual(db, usuario)
    return db.query(Matricula).filter(Matricula.oferente_id == oferente.id_oferente).order_by(Matricula.tipo_profesional).all()


@router.get(
    "/validaciones",
    response_model=list[ValidacionHistorialOut],
    summary="Historial de intentos de validación, incluidos los fallidos",
    responses=RESPUESTAS_COMUNES,
)
def listar_validaciones(db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    oferente = _oferente_actual(db, usuario)
    return (
        db.query(ValidacionMatricula)
        .filter(ValidacionMatricula.oferente_id == oferente.id_oferente)
        .order_by(ValidacionMatricula.fecha_intento.desc(), ValidacionMatricula.id_validacion.desc())
        .all()
    )

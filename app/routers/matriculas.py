from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.errores import error_negocio, error_validacion
from app.db.database import get_db
from app.models.matricula import Matricula, ValidacionMatricula
from app.models.oferente import Oferente
from app.models.usuario import Usuario
from app.schemas.matricula import (
    MatriculaOut,
    TipoMatriculaOut,
    ValidacionHistorialOut,
    ValidacionMatriculaIn,
    ValidacionMatriculaOut,
)
from app.services.matriculas import MENSAJES_RESULTADO, RANGO_DIGITOS_POR_TIPO, validar_matricula

router = APIRouter(prefix="/api/v1/oferentes/me/matriculas", tags=["Matrículas"])

RESPUESTAS_COMUNES = {
    401: {"description": "Falta token o es inválido"},
    403: {"description": "Falta completar el registro de Profesional (`registro_incompleto`)"},
}


def _oferente_actual(db: Session, usuario: Usuario) -> Oferente:
    """Mismo criterio que el guard de HU-04: sin perfil no hay matrículas que
    fidelizar, y el error es el mismo código que en el resto de la API."""
    oferente = db.get(Oferente, usuario.id_usuario)
    if not oferente:
        raise error_negocio(status.HTTP_403_FORBIDDEN, "registro_incompleto", "Completá el registro de Profesional para continuar")
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
    **síncrona**, contra el padrón cargado en la base. Devuelve un código de
    `resultado` con su mensaje; el frontend lo renderiza.

    **CA03:** si la consulta al padrón no responde en
    `MATRICULA_TIMEOUT_SEGUNDOS` (60 por defecto), el resultado es `Timeout`.
    **Para QA:** la matrícula trampa —`9999999999` para Gasista, `99999999`
    para Aire acondicionado— simula un padrón que no responde, así que la
    respuesta `Timeout` llega recién al cumplirse ese tiempo.
    """
    minimo, maximo = RANGO_DIGITOS_POR_TIPO[payload.tipo_profesional]
    numero = payload.numero_matricula
    if numero and not numero.isdigit():
        raise error_validacion("numero_matricula", "solo_digitos", "El número de matrícula solo puede tener dígitos")
    if not (minimo <= len(numero) <= maximo):
        if minimo == maximo:
            raise error_validacion("numero_matricula", "digitos_invalidos", f"Debe ingresar {maximo} dígitos")
        raise error_validacion(
            "numero_matricula", "digitos_invalidos", f"Debe ingresar entre {minimo} y {maximo} dígitos"
        )

    oferente = _oferente_actual(db, usuario)
    validacion = validar_matricula(db, oferente, payload.tipo_profesional, payload.numero_matricula)
    db.commit()

    matricula = _matricula_vigente(db, oferente.id_oferente, payload.tipo_profesional)
    return ValidacionMatriculaOut(resultado=validacion.resultado, mensaje=MENSAJES_RESULTADO[validacion.resultado], matricula=matricula)


@router.get(
    "/tipos",
    response_model=list[TipoMatriculaOut],
    summary="Tipos de profesional que se pueden fidelizar y los dígitos de su matrícula",
    responses={401: {"description": "Falta token o es inválido"}},
)
def listar_tipos(usuario: Usuario = Depends(get_current_user)):
    """HU-02 / CA01 — Alimenta el selector "Tipo de profesional", en orden
    alfabético (la primera opción es la que viene por defecto), y el label
    de dígitos del número de matrícula (`digitos_min`-`digitos`)."""
    return [
        TipoMatriculaOut(tipo_profesional=tipo, digitos=maximo, digitos_min=minimo)
        for tipo, (minimo, maximo) in sorted(RANGO_DIGITOS_POR_TIPO.items())
    ]


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

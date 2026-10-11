from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_oferente_registrado
from app.core.errores import error_negocio
from app.db.database import get_db
from app.models.oferente import Oferente
from app.models.usuario import EstadoCuenta, Usuario
from app.schemas.oferente import OferenteEdicion, OferentePrivadoOut, OferentePublicoOut, OferenteRegistro
from app.services.oferentes import aplicar_edicion, armar_privada, armar_publica, crear_oferente

router = APIRouter(prefix="/api/v1/oferentes", tags=["Oferentes"])

RESPUESTAS_REGISTRO = {
    401: {"description": "Falta token o es inválido"},
    403: {"description": "El usuario es Administrador (`rol_invalido`) o no tiene perfil (`registro_incompleto`)"},
}


@router.get(
    "",
    response_model=list[OferentePublicoOut],
    summary="Buscar profesionales (público)",
)
def buscar_oferentes(
    q: str | None = Query(default=None, description="Palabra clave: parte del nombre"),
    categoria_id: int | None = Query(default=None, description="Filtrar por categoría/oficio"),
    db: Session = Depends(get_db),
):
    """RF7/RF8 — Búsqueda pública. Excluye las cuentas suspendidas o bloqueadas
    (observación F4 de QA): un Profesional suspendido no aparece."""
    query = db.query(Oferente).join(Usuario, Usuario.id_usuario == Oferente.id_oferente).filter(
        Usuario.estado_cuenta == EstadoCuenta.ACTIVA
    )
    if categoria_id:
        query = query.filter(Oferente.categoria_id == categoria_id)
    if q:
        like = f"%{q}%"
        query = query.filter(Oferente.nombre.ilike(like))
    return [armar_publica(db, oferente) for oferente in query.all()]


@router.post(
    "",
    response_model=OferentePrivadoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Confirmar el registro de Profesional (CA02/CA03)",
    responses={
        **RESPUESTAS_REGISTRO,
        409: {"description": "Ya completó el registro (`perfil_existente`) o el DNI/CUIT ya existe (`dni_cuit_duplicado`)"},
        422: {"description": "Errores de validación. `errores[]` trae todos los campos a corregir"},
    },
)
def crear_perfil_oferente(
    payload: OferenteRegistro,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """HU-04 — Crea el perfil del Oferente y sus días de atención en una sola
    transacción. Si el formulario tiene errores, responde 422 con **todos** los
    campos a la vez (CA02). Si abandonan el formulario, no se persiste nada (CA06)."""
    oferente = crear_oferente(db, usuario, payload)
    return armar_privada(db, oferente)


@router.get(
    "/me",
    response_model=OferentePrivadoOut,
    summary="Mi perfil profesional completo",
    responses=RESPUESTAS_REGISTRO,
)
def obtener_mi_perfil(oferente: Oferente = Depends(get_oferente_registrado), db: Session = Depends(get_db)):
    """HU-04 CA04 — Perfil del dueño: incluye DNI/CUIT, que nadie más ve (D7)."""
    return armar_privada(db, oferente)


@router.put(
    "/me",
    response_model=OferentePrivadoOut,
    summary="Editar mi perfil profesional (sin DNI/CUIT ni correo)",
    responses={
        **RESPUESTAS_REGISTRO,
        409: {"description": "Cambio de nombre con una matrícula fidelizada (`nombre_bloqueado_por_matricula`)"},
        422: {"description": "Errores de validación, o un campo que no se puede editar (dni_cuit)"},
    },
)
def actualizar_mi_perfil(
    payload: OferenteEdicion,
    oferente: Oferente = Depends(get_oferente_registrado),
    db: Session = Depends(get_db),
):
    """HU-04 (D18) — Todos los campos son opcionales. El DNI/CUIT y el correo no
    se cambian: se rechazan o se ignoran."""
    actualizado = aplicar_edicion(db, oferente, payload)
    return armar_privada(db, actualizado)


@router.get(
    "/{oferente_id}",
    response_model=OferentePublicoOut,
    summary="Consultar el perfil de un profesional (público)",
    responses={404: {"description": "Oferente no encontrado"}},
)
def obtener_oferente(oferente_id: int, db: Session = Depends(get_db)):
    """RF7 — Perfil público. No devuelve DNI/CUIT, estado de verificación ni
    rechazos acumulados."""
    oferente = db.get(Oferente, oferente_id)
    if not oferente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Oferente no encontrado")
    return armar_publica(db, oferente)


@router.put(
    "/{oferente_id}",
    response_model=OferentePrivadoOut,
    summary="Editar el perfil propio (alias de compatibilidad de PUT /me)",
    responses={
        **RESPUESTAS_REGISTRO,
        403: {"description": "El perfil no es el del usuario autenticado"},
    },
)
def actualizar_perfil_oferente(
    oferente_id: int,
    payload: OferenteEdicion,
    oferente: Oferente = Depends(get_oferente_registrado),
    db: Session = Depends(get_db),
):
    """Se mantiene por compatibilidad con los llamados de Sprint 1. Delega en la
    misma lógica que `PUT /oferentes/me` y solo acepta el propio `id`."""
    if oferente.id_oferente != oferente_id:
        raise error_negocio(403, "no_autorizado", "No autorizado")
    actualizado = aplicar_edicion(db, oferente, payload)
    return armar_privada(db, actualizado)

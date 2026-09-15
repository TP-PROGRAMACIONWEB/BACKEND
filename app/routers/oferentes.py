from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.database import get_db
from app.models.oferente import Oferente
from app.models.usuario import RolUsuario, Usuario
from app.schemas.oferente import OferenteCreate, OferenteOut, OferenteUpdate

router = APIRouter(prefix="/api/v1/oferentes", tags=["Oferentes"])


@router.get("", response_model=list[OferenteOut], summary="Buscar profesionales (público)")
def buscar_oferentes(
    q: str | None = Query(default=None, description="Palabra clave: nombre o apellido"),
    categoria_id: int | None = Query(default=None, description="Filtrar por categoría/oficio"),
    db: Session = Depends(get_db),
):
    """RF7/RF8 — Búsqueda y consulta pública de perfiles profesionales. No requiere login."""
    query = db.query(Oferente)
    if categoria_id:
        query = query.filter(Oferente.categoria_id == categoria_id)
    if q:
        like = f"%{q}%"
        query = query.filter((Oferente.nombre.ilike(like)) | (Oferente.apellido.ilike(like)))
    return query.all()


@router.get(
    "/{oferente_id}",
    response_model=OferenteOut,
    summary="Consultar el perfil de un profesional (público)",
    responses={404: {"description": "Oferente no encontrado"}},
)
def obtener_oferente(oferente_id: int, db: Session = Depends(get_db)):
    """RF7 — Consulta pública de perfil profesional. No requiere login."""
    oferente = db.get(Oferente, oferente_id)
    if not oferente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Oferente no encontrado")
    return oferente


@router.post(
    "",
    response_model=OferenteOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear el perfil profesional del usuario autenticado",
    responses={
        401: {"description": "Falta token o es inválido"},
        403: {"description": "El usuario autenticado no tiene rol Oferente"},
        409: {"description": "El usuario ya tiene perfil, o el DNI/CUIT ya está registrado"},
        422: {"description": "Campo obligatorio faltante o DNI/CUIT/teléfono con formato inválido"},
    },
)
def crear_perfil_oferente(
    payload: OferenteCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """RF2/HU-02 — Creación del perfil profesional del oferente. El
    `id_oferente` resultante es siempre igual al `id_usuario` del usuario
    autenticado (comparten clave primaria)."""
    if usuario.rol != RolUsuario.OFERENTE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo los usuarios con rol Oferente pueden crear un perfil")
    if usuario.oferente:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El usuario ya tiene un perfil de oferente")
    if db.query(Oferente).filter(Oferente.dni_cuit == payload.dni_cuit).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El DNI/CUIT ya está registrado")

    oferente = Oferente(id_oferente=usuario.id_usuario, **payload.model_dump())
    db.add(oferente)
    db.commit()
    db.refresh(oferente)
    return oferente


@router.put(
    "/{oferente_id}",
    response_model=OferenteOut,
    summary="Editar el perfil profesional propio",
    responses={
        401: {"description": "Falta token o es inválido"},
        403: {"description": "El usuario autenticado no es el dueño del perfil"},
        404: {"description": "Oferente no encontrado"},
    },
)
def actualizar_perfil_oferente(
    oferente_id: int,
    payload: OferenteUpdate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """RF2 — Edición del perfil profesional. Solo el dueño puede editarlo."""
    oferente = db.get(Oferente, oferente_id)
    if not oferente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Oferente no encontrado")
    if oferente.id_oferente != usuario.id_usuario:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(oferente, field, value)

    db.commit()
    db.refresh(oferente)
    return oferente

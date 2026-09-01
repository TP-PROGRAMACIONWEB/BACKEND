from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.database import get_db
from app.models.oferente import Oferente
from app.models.usuario import RolUsuario, Usuario
from app.schemas.oferente import OferenteCreate, OferenteOut, OferenteUpdate

router = APIRouter(prefix="/api/v1/oferentes", tags=["Oferentes"])


@router.get("", response_model=list[OferenteOut])
def buscar_oferentes(
    q: str | None = Query(default=None, description="Palabra clave: nombre, apellido u oficio"),
    categoria_id: int | None = None,
    db: Session = Depends(get_db),
):
    """RF7/RF8 — Búsqueda y consulta pública de perfiles profesionales."""
    query = db.query(Oferente)
    if categoria_id:
        query = query.filter(Oferente.categoria_id == categoria_id)
    if q:
        like = f"%{q}%"
        query = query.filter((Oferente.nombre.ilike(like)) | (Oferente.apellido.ilike(like)))
    return query.all()


@router.get("/{oferente_id}", response_model=OferenteOut)
def obtener_oferente(oferente_id: int, db: Session = Depends(get_db)):
    """RF7 — Consulta pública de perfil profesional."""
    oferente = db.get(Oferente, oferente_id)
    if not oferente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Oferente no encontrado")
    return oferente


@router.post("", response_model=OferenteOut, status_code=status.HTTP_201_CREATED)
def crear_perfil_oferente(
    payload: OferenteCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """RF2/HU-02 — Creación del perfil profesional del oferente."""
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


@router.put("/{oferente_id}", response_model=OferenteOut)
def actualizar_perfil_oferente(
    oferente_id: int,
    payload: OferenteUpdate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """RF2 — Edición del perfil profesional."""
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

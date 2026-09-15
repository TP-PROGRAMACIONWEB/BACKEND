from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import require_admin
from app.db.database import get_db
from app.models.categoria import Categoria
from app.schemas.categoria import CategoriaCreate, CategoriaOut, CategoriaUpdate

router = APIRouter(prefix="/api/v1/categorias", tags=["Categorías"])


@router.get("", response_model=list[CategoriaOut], summary="Listar categorías/oficios (público)")
def listar_categorias(db: Session = Depends(get_db)):
    """RF5 — Navegación pública, sin login requerido."""
    return db.query(Categoria).all()


@router.post(
    "",
    response_model=CategoriaOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
    summary="Crear categoría (solo Administrador)",
    responses={401: {"description": "Falta token"}, 403: {"description": "Requiere rol Administrador"}},
)
def crear_categoria(payload: CategoriaCreate, db: Session = Depends(get_db)):
    """RF18 — Administración de categorías de oficios."""
    categoria = Categoria(**payload.model_dump())
    db.add(categoria)
    db.commit()
    db.refresh(categoria)
    return categoria


@router.put(
    "/{categoria_id}",
    response_model=CategoriaOut,
    dependencies=[Depends(require_admin)],
    summary="Editar categoría (solo Administrador)",
    responses={
        401: {"description": "Falta token"},
        403: {"description": "Requiere rol Administrador"},
        404: {"description": "Categoría no encontrada"},
    },
)
def actualizar_categoria(categoria_id: int, payload: CategoriaUpdate, db: Session = Depends(get_db)):
    """RF18."""
    categoria = db.get(Categoria, categoria_id)
    if not categoria:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Categoría no encontrada")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(categoria, field, value)

    db.commit()
    db.refresh(categoria)
    return categoria


@router.delete(
    "/{categoria_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
    summary="Eliminar categoría (solo Administrador)",
    responses={
        401: {"description": "Falta token"},
        403: {"description": "Requiere rol Administrador"},
        404: {"description": "Categoría no encontrada"},
    },
)
def eliminar_categoria(categoria_id: int, db: Session = Depends(get_db)):
    """RF18."""
    categoria = db.get(Categoria, categoria_id)
    if not categoria:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Categoría no encontrada")

    db.delete(categoria)
    db.commit()

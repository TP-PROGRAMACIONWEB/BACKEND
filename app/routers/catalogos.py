from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.catalogos import DIAS, EXPERIENCIA, HORARIO_POR_DEFECTO
from app.core.config import settings
from app.db.database import get_db
from app.models.categoria import Categoria, EstadoCategoria
from app.schemas.catalogo import (
    CatalogoRegistroOut,
    CategoriaCatalogo,
    DiaCatalogo,
    ExperienciaCatalogo,
    HorarioPorDefecto,
    LimitesCatalogo,
)

router = APIRouter(prefix="/api/v1/catalogos", tags=["Catálogos"])


@router.get(
    "/registro-oferente",
    response_model=CatalogoRegistroOut,
    summary="Opciones del formulario de registro de Profesional (público)",
)
def catalogo_registro_oferente(db: Session = Depends(get_db)):
    """HU-04 — Una sola llamada llena categorías, rangos de experiencia, días,
    horario por defecto y los límites de trabajos realizados. Solo se listan las
    categorías activas."""
    categorias = (
        db.query(Categoria)
        .filter(Categoria.estado == EstadoCategoria.ACTIVA)
        .order_by(Categoria.nombre)
        .all()
    )
    return CatalogoRegistroOut(
        categorias=[CategoriaCatalogo(id=categoria.id_categoria, nombre=categoria.nombre) for categoria in categorias],
        experiencia=[ExperienciaCatalogo(codigo=rango.codigo, etiqueta=rango.etiqueta) for rango in EXPERIENCIA],
        dias=[DiaCatalogo(dia=dia, corto=corto, largo=largo) for dia, corto, largo in DIAS],
        horario_default=HorarioPorDefecto(**HORARIO_POR_DEFECTO),
        limites=LimitesCatalogo(
            trabajos=settings.trabajos_maximos,
            fotos_por_trabajo=settings.fotos_por_trabajo_maximas,
            tamano_maximo_mb=settings.archivo_tamano_maximo_mb,
        ),
    )

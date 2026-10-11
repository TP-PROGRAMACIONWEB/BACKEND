from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.deps import get_oferente_registrado
from app.db.database import get_db
from app.models.oferente import Oferente
from app.models.trabajo_realizado import TrabajoRealizado
from app.schemas.trabajo import TrabajoCreate, TrabajoOut
from app.services.archivos import armar_trabajo, crear_trabajo, eliminar_trabajo
from app.services.storage import StorageService, get_storage_service

router = APIRouter(prefix="/api/v1/oferentes", tags=["Oferentes"])


@router.get(
    "/{oferente_id}/trabajos",
    response_model=list[TrabajoOut],
    summary="Trabajos realizados de un Profesional (público)",
    responses={404: {"description": "Oferente no encontrado"}},
)
def listar_trabajos(oferente_id: int, db: Session = Depends(get_db)):
    """HU-04 T06 — Más nuevos primero. Cada trabajo trae la foto principal y la
    lista completa de fotos ordenadas, así la tarjeta y el carrusel no necesitan
    un segundo request."""
    if db.get(Oferente, oferente_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Oferente no encontrado")
    trabajos = (
        db.query(TrabajoRealizado)
        .filter(TrabajoRealizado.oferente_id == oferente_id)
        .order_by(TrabajoRealizado.fecha_creacion.desc(), TrabajoRealizado.id_trabajo.desc())
        .all()
    )
    return [armar_trabajo(trabajo) for trabajo in trabajos]


@router.post(
    "/me/trabajos",
    response_model=TrabajoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Cargar un trabajo realizado con sus fotos",
    responses={
        401: {"description": "Falta token o es inválido"},
        403: {"description": "Falta completar el registro de Profesional (`registro_incompleto`)"},
        409: {"description": "Ya hay 5 trabajos cargados (`limite_trabajos`)"},
        422: {"description": "Sin descripción, fotos fuera de rango, o una foto que no corresponde"},
        503: {"description": "Supabase Storage no está configurado"},
    },
)
def cargar_trabajo(
    payload: TrabajoCreate,
    oferente: Oferente = Depends(get_oferente_registrado),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
):
    """HU-04 T06 — Obligatorios: al menos una foto y la descripción. El título es
    opcional. Las fotos se guardan en el orden del body; la primera es la principal."""
    trabajo = crear_trabajo(db, storage, oferente.id_oferente, payload)
    return armar_trabajo(trabajo)


@router.delete(
    "/me/trabajos/{id_trabajo}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Borrar un trabajo realizado (filas y fotos)",
    responses={
        401: {"description": "Falta token o es inválido"},
        403: {"description": "Falta completar el registro de Profesional (`registro_incompleto`)"},
        404: {"description": "No existe un trabajo tuyo con ese id"},
        503: {"description": "Supabase Storage no está configurado"},
    },
)
def borrar_trabajo(
    id_trabajo: int,
    oferente: Oferente = Depends(get_oferente_registrado),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
):
    """Caso A53 — Borra las filas y los objetos de Storage. Un trabajo ajeno da
    404, para no revelar que existe."""
    trabajo = db.get(TrabajoRealizado, id_trabajo)
    if trabajo is None or trabajo.oferente_id != oferente.id_oferente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trabajo no encontrado")
    eliminar_trabajo(db, storage, trabajo)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

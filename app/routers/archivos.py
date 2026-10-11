from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.deps import get_oferente_registrado
from app.db.database import get_db
from app.models.archivo_adjunto import TipoArchivo
from app.models.oferente import Oferente
from app.schemas.archivo import ArchivoRefIn, SubidaIn, SubidaOut
from app.schemas.oferente import OferentePrivadoOut
from app.services.archivos import eliminar_imagen_unica, preparar_subida, reemplazar_imagen_unica
from app.services.oferentes import armar_privada
from app.services.storage import StorageService, get_storage_service

router = APIRouter(prefix="/api/v1/oferentes/me", tags=["Oferentes"])

RESPUESTAS_ARCHIVOS = {
    401: {"description": "Falta token o es inválido"},
    403: {"description": "Falta completar el registro de Profesional (`registro_incompleto`)"},
    422: {"description": "Formato distinto de JPG/PNG, más de 5 MB, o un path que no corresponde (`archivo_invalido`)"},
    503: {"description": "Supabase Storage no está configurado"},
}


@router.post(
    "/archivos/subidas",
    response_model=SubidaOut,
    status_code=status.HTTP_201_CREATED,
    summary="Pedir una URL firmada para subir una imagen (paso 1)",
    responses=RESPUESTAS_ARCHIVOS,
)
def pedir_subida(
    payload: SubidaIn,
    oferente: Oferente = Depends(get_oferente_registrado),
    storage: StorageService = Depends(get_storage_service),
):
    """HU-04 T06 — Valida tipo y tamaño antes de firmar, para dar el error
    temprano. El navegador después sube el archivo directo a `upload_url`, y
    luego confirma con el endpoint que corresponda usando el `path`."""
    return preparar_subida(storage, oferente.id_oferente, payload.tipo, payload.content_type, payload.tamano_bytes)


@router.put(
    "/foto-perfil",
    response_model=OferentePrivadoOut,
    summary="Confirmar la foto de perfil (paso 3)",
    responses=RESPUESTAS_ARCHIVOS,
)
def confirmar_foto_perfil(
    payload: ArchivoRefIn,
    oferente: Oferente = Depends(get_oferente_registrado),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
):
    """Reemplaza la foto anterior. Vuelve a verificar el objeto real en Storage."""
    reemplazar_imagen_unica(db, storage, oferente.id_oferente, TipoArchivo.PERFIL, payload.path)
    db.refresh(oferente)
    return armar_privada(db, oferente)


@router.delete(
    "/foto-perfil",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Quitar la foto de perfil (vuelve a las iniciales)",
    responses=RESPUESTAS_ARCHIVOS,
)
def quitar_foto_perfil(
    oferente: Oferente = Depends(get_oferente_registrado),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
):
    eliminar_imagen_unica(db, storage, oferente.id_oferente, TipoArchivo.PERFIL)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/portada",
    response_model=OferentePrivadoOut,
    summary="Confirmar la imagen de portada (paso 3)",
    responses=RESPUESTAS_ARCHIVOS,
)
def confirmar_portada(
    payload: ArchivoRefIn,
    oferente: Oferente = Depends(get_oferente_registrado),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
):
    reemplazar_imagen_unica(db, storage, oferente.id_oferente, TipoArchivo.PORTADA, payload.path)
    db.refresh(oferente)
    return armar_privada(db, oferente)

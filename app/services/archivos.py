"""Subida y confirmación de imágenes (HU-04 T06).

Flujo en tres pasos, con el backend como autoridad:

1. `preparar_subida`: valida tipo y tamaño **antes** de firmar y arma el path.
   El path lo decide el backend, nunca el cliente.
2. El navegador hace el PUT del archivo a la URL firmada (Supabase, directo).
3. `validar_objeto_subido`: al confirmar, se vuelve a mirar el objeto real en
   Storage. El cliente pudo mentir en el paso 1, así que el tamaño y el MIME
   que cuentan son los que reporta el bucket.
"""

import re
import uuid

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errores import error_negocio, error_validacion
from app.models.archivo_adjunto import ArchivoAdjunto, TipoArchivo
from app.models.trabajo_realizado import TrabajoRealizado
from app.schemas.archivo import SubidaOut
from app.schemas.trabajo import TrabajoCreate, TrabajoOut, FotoTrabajoOut
from app.services.storage import ObjetoStorage, StorageService, url_publica

MIME_PERMITIDOS = {"image/jpeg": "jpg", "image/png": "png"}
DIRECTORIO_POR_TIPO = {TipoArchivo.PERFIL: "perfil", TipoArchivo.PORTADA: "portada", TipoArchivo.TRABAJO: "trabajo"}

# oferentes/{id}/{tipo}/{32 hex}.{ext}: el formato exacto que genera el backend.
PATRON_PATH = re.compile(r"oferentes/(\d+)/(perfil|portada|trabajo)/[0-9a-f]{32}\.(jpg|png)")


def validar_tipo_y_tamano(content_type: str, tamano_bytes: int) -> None:
    if content_type not in MIME_PERMITIDOS:
        raise error_validacion("content_type", "formato_imagen_invalido", "Formato de imagen incorrecto, solo se acepta JPG o PNG")
    if tamano_bytes <= 0:
        raise error_validacion("tamano_bytes", "archivo_vacio", "El archivo está vacío")
    if tamano_bytes > settings.archivo_tamano_maximo_bytes:
        raise error_validacion(
            "tamano_bytes",
            "imagen_demasiado_grande",
            f"Supera el tamaño permitido, solo se acepta hasta {settings.archivo_tamano_maximo_mb}MB",
        )


def preparar_subida(storage: StorageService, oferente_id: int, tipo: str, content_type: str, tamano_bytes: int) -> SubidaOut:
    validar_tipo_y_tamano(content_type, tamano_bytes)
    path = f"oferentes/{oferente_id}/{DIRECTORIO_POR_TIPO[tipo]}/{uuid.uuid4().hex}.{MIME_PERMITIDOS[content_type]}"
    return SubidaOut(path=path, upload_url=storage.crear_url_subida(path, content_type), tipo=tipo, content_type=content_type)


def validar_objeto_subido(db: Session, storage: StorageService, oferente_id: int, tipo: str, path: str) -> ObjetoStorage:
    """Confirma que el archivo subido es de este Oferente, de este tipo, todavía
    no está registrado, y que su tamaño y MIME reales cumplen las reglas."""
    coincide = PATRON_PATH.fullmatch(path)
    if not coincide or not path.startswith(f"oferentes/{oferente_id}/{DIRECTORIO_POR_TIPO[tipo]}/"):
        raise error_validacion("path", "archivo_invalido", "El archivo no corresponde a este perfil")

    if db.query(ArchivoAdjunto.id_archivo).filter(ArchivoAdjunto.storage_path == path).first():
        raise error_validacion("path", "archivo_invalido", "Ese archivo ya está asociado a un perfil")

    objeto = storage.obtener_objeto(path)
    if objeto is None:
        raise error_validacion("path", "archivo_invalido", "El archivo todavía no se subió")
    if objeto.content_type not in MIME_PERMITIDOS:
        raise error_validacion("path", "formato_imagen_invalido", "Formato de imagen incorrecto, solo se acepta JPG o PNG")
    if objeto.tamano_bytes > settings.archivo_tamano_maximo_bytes:
        raise error_validacion(
            "path",
            "imagen_demasiado_grande",
            f"Supera el tamaño permitido, solo se acepta hasta {settings.archivo_tamano_maximo_mb}MB",
        )
    return objeto


def reemplazar_imagen_unica(db: Session, storage: StorageService, oferente_id: int, tipo: str, path: str) -> None:
    """Foto de perfil o portada: la nueva reemplaza a la anterior. La fila se
    guarda primero; el objeto viejo se borra después, y si Storage falla queda
    huérfano en el bucket sin afectar al perfil."""
    objeto = validar_objeto_subido(db, storage, oferente_id, tipo, path)
    anteriores = (
        db.query(ArchivoAdjunto)
        .filter(ArchivoAdjunto.oferente_id == oferente_id, ArchivoAdjunto.tipo == tipo, ArchivoAdjunto.trabajo_id.is_(None))
        .all()
    )
    rutas_viejas = [archivo.storage_path for archivo in anteriores]
    for archivo in anteriores:
        db.delete(archivo)
    db.add(
        ArchivoAdjunto(
            oferente_id=oferente_id,
            tipo=tipo,
            storage_path=path,
            content_type=objeto.content_type,
            tamano_bytes=objeto.tamano_bytes,
        )
    )
    db.commit()
    _borrar_objetos_huerfanos(storage, rutas_viejas)


def _borrar_objetos_huerfanos(storage: StorageService, rutas: list[str]) -> None:
    """Limpieza que no debe tumbar la respuesta: si Storage no responde, el
    objeto queda en el bucket y se limpia con el cron fuera de este sprint."""
    if not rutas:
        return
    try:
        storage.eliminar(rutas)
    except Exception:  # noqa: BLE001 — la fila ya está confirmada; el borrado es best-effort
        pass


def eliminar_imagen_unica(db: Session, storage: StorageService, oferente_id: int, tipo: str) -> None:
    anteriores = (
        db.query(ArchivoAdjunto)
        .filter(ArchivoAdjunto.oferente_id == oferente_id, ArchivoAdjunto.tipo == tipo, ArchivoAdjunto.trabajo_id.is_(None))
        .all()
    )
    rutas = [archivo.storage_path for archivo in anteriores]
    # Primero Storage: si falla, la base no cambia y el usuario puede reintentar.
    storage.eliminar(rutas)
    for archivo in anteriores:
        db.delete(archivo)
    db.commit()


def cantidad_trabajos(db: Session, oferente_id: int) -> int:
    return db.query(func.count(TrabajoRealizado.id_trabajo)).filter(TrabajoRealizado.oferente_id == oferente_id).scalar()


def armar_trabajo(trabajo: TrabajoRealizado) -> TrabajoOut:
    """Una sola forma para la tarjeta (A50) y para el carrusel (A51)."""
    fotos = [FotoTrabajoOut(orden=foto.orden, url=url_publica(foto.storage_path)) for foto in trabajo.fotos]
    return TrabajoOut(
        id_trabajo=trabajo.id_trabajo,
        titulo=trabajo.titulo,
        descripcion=trabajo.descripcion,
        fecha_creacion=trabajo.fecha_creacion,
        foto_principal_url=fotos[0].url if fotos else None,
        fotos=fotos,
    )


def crear_trabajo(db: Session, storage: StorageService, oferente_id: int, datos: TrabajoCreate) -> TrabajoRealizado:
    if cantidad_trabajos(db, oferente_id) >= settings.trabajos_maximos:
        raise error_negocio(409, "limite_trabajos", f"Ya cargaste el máximo de {settings.trabajos_maximos} trabajos")

    objetos = [validar_objeto_subido(db, storage, oferente_id, TipoArchivo.TRABAJO, path) for path in datos.fotos]

    trabajo = TrabajoRealizado(oferente_id=oferente_id, titulo=datos.titulo, descripcion=datos.descripcion)
    db.add(trabajo)
    db.flush()
    # El orden de la lista que manda el frontend es el orden de las fotos (A50):
    # la primera es la foto principal.
    for orden, (path, objeto) in enumerate(zip(datos.fotos, objetos), start=1):
        db.add(
            ArchivoAdjunto(
                oferente_id=oferente_id,
                tipo=TipoArchivo.TRABAJO,
                storage_path=path,
                content_type=objeto.content_type,
                tamano_bytes=objeto.tamano_bytes,
                trabajo_id=trabajo.id_trabajo,
                orden=orden,
            )
        )
    db.commit()
    db.refresh(trabajo)
    return trabajo


def eliminar_trabajo(db: Session, storage: StorageService, trabajo: TrabajoRealizado) -> None:
    """Caso A53: borra las filas y los objetos. Primero Storage, igual que en
    las imágenes únicas: si falla, la base no cambia."""
    storage.eliminar([foto.storage_path for foto in trabajo.fotos])
    db.delete(trabajo)
    db.commit()

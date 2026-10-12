"""Almacenamiento de imágenes en Supabase Storage (HU-04 T06, D4).

Las fotos **no** pasan por el backend: el navegador sube directo al bucket con
una URL firmada que emite el backend. Eso evita el límite de ~4,5 MB por request
de Vercel y el disco efímero de las funciones serverless.

El servicio se expone como dependencia de FastAPI (`get_storage_service`), igual
que el de correo: los tests lo reemplazan por `StorageServiceFake` y la suite
nunca toca Supabase de verdad.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import quote

import httpx
from fastapi import HTTPException, status

from app.core.config import settings


class StorageError(Exception):
    """Supabase no respondió bien. Se traduce a 502 en el router."""


@dataclass(frozen=True)
class ObjetoStorage:
    path: str
    tamano_bytes: int
    content_type: str


def url_publica(path: str) -> str:
    """URL de lectura del bucket público. Se arma a partir del path; nunca se
    guarda en la base."""
    base = settings.supabase_url.rstrip("/")
    return f"{base}/storage/v1/object/public/{settings.supabase_storage_bucket}/{quote(path)}"


class StorageService(ABC):
    @abstractmethod
    def crear_url_subida(self, path: str, content_type: str) -> str:
        """URL firmada a la que el navegador hace el PUT del archivo."""

    @abstractmethod
    def obtener_objeto(self, path: str) -> ObjetoStorage | None:
        """Metadatos reales del objeto subido, o None si todavía no existe."""

    @abstractmethod
    def eliminar(self, paths: list[str]) -> None:
        """Borra objetos del bucket. Una lista vacía no hace nada."""


class SupabaseStorageService(StorageService):
    """Cliente HTTP contra la API REST de Storage, con la service role key.
    La clave nunca sale del backend."""

    def __init__(self, url: str, service_role_key: str, bucket: str, timeout: float = 10.0):
        self.base = f"{url.rstrip('/')}/storage/v1"
        self.bucket = bucket
        self.timeout = timeout
        self.headers = {"apikey": service_role_key, "Authorization": f"Bearer {service_role_key}"}

    def _pedir(self, metodo: str, ruta: str, **kwargs) -> httpx.Response:
        try:
            respuesta = httpx.request(metodo, f"{self.base}{ruta}", headers=self.headers, timeout=self.timeout, **kwargs)
        except httpx.HTTPError as exc:
            raise StorageError(f"No se pudo contactar a Supabase Storage: {exc}") from exc
        return respuesta

    def crear_url_subida(self, path: str, content_type: str) -> str:
        respuesta = self._pedir("POST", f"/object/upload/sign/{self.bucket}/{quote(path)}")
        if respuesta.status_code >= 400:
            raise StorageError(f"Supabase rechazó la URL de subida (HTTP {respuesta.status_code})")
        # Supabase devuelve una ruta relativa a /storage/v1, que ya trae el token.
        return f"{self.base}{respuesta.json()['url']}"

    def obtener_objeto(self, path: str) -> ObjetoStorage | None:
        respuesta = self._pedir("GET", f"/object/info/{self.bucket}/{quote(path)}")
        if respuesta.status_code == 404:
            return None
        if respuesta.status_code >= 400:
            raise StorageError(f"Supabase no pudo leer el objeto (HTTP {respuesta.status_code})")
        datos = respuesta.json()
        metadatos = datos.get("metadata") or {}
        return ObjetoStorage(
            path=path,
            tamano_bytes=int(metadatos.get("size", datos.get("size", 0))),
            content_type=metadatos.get("mimetype", datos.get("mimetype", "")),
        )

    def eliminar(self, paths: list[str]) -> None:
        if not paths:
            return
        respuesta = self._pedir("DELETE", f"/object/{self.bucket}", json={"prefixes": paths})
        if respuesta.status_code >= 400:
            raise StorageError(f"Supabase no pudo borrar los objetos (HTTP {respuesta.status_code})")


class StorageServiceFake(StorageService):
    """Doble para tests y desarrollo sin credenciales. `subir` simula el PUT
    que haría el navegador contra la URL firmada."""

    def __init__(self):
        self.objetos: dict[str, ObjetoStorage] = {}
        self.eliminados: list[str] = []

    def crear_url_subida(self, path: str, content_type: str) -> str:
        return f"https://storage.fake/upload/{path}?token=fake"

    def subir(self, path: str, tamano_bytes: int, content_type: str) -> None:
        self.objetos[path] = ObjetoStorage(path=path, tamano_bytes=tamano_bytes, content_type=content_type)

    def obtener_objeto(self, path: str) -> ObjetoStorage | None:
        return self.objetos.get(path)

    def eliminar(self, paths: list[str]) -> None:
        for path in paths:
            self.objetos.pop(path, None)
        self.eliminados.extend(paths)


@lru_cache
def _servicio_supabase() -> SupabaseStorageService:
    return SupabaseStorageService(
        url=settings.supabase_url,
        service_role_key=settings.supabase_service_role_key,
        bucket=settings.supabase_storage_bucket,
    )


def get_storage_service() -> StorageService:
    """Dependencia de FastAPI. Sin credenciales responde 503, igual que Auth0:
    el resto del backend sigue funcionando."""
    if not settings.supabase_habilitado:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"codigo": "storage_no_configurado", "mensaje": "El almacenamiento de imágenes no está configurado"},
        )
    return _servicio_supabase()

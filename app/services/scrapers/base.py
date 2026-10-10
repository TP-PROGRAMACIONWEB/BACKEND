"""Base común: HTTP educado + FilaPadronExterna + logs para auditoría (CA04)."""

from __future__ import annotations

import hashlib
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import date

import httpx

USER_AGENT = "OffixBot/1.0 (UTN-FRSF academico; padron matriculas)"


@dataclass
class FilaPadronExterna:
    tipo_profesional: str  # "Gasista" | "Aire acondicionado"
    numero_matricula: str
    nombre_matriculado: str
    categoria: str
    fecha_vencimiento: date
    fuente: str = ""


def normalizar_texto(texto: str) -> str:
    sin_acentos = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    sin_puntuacion = re.sub(r"[^\w\s]", " ", sin_acentos.upper())
    return " ".join(sin_puntuacion.split())


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch_texto(url: str, timeout: float = 20.0, params: dict | None = None) -> str:
    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=timeout, follow_redirects=True) as c:
        r = c.get(url, params=params)
        r.raise_for_status()
        return r.text


def fetch_bytes(url: str, timeout: float = 30.0) -> bytes:
    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=timeout, follow_redirects=True) as c:
        r = c.get(url)
        r.raise_for_status()
        return r.content


def dormir_cortesia(segundos: float = 2.0):
    time.sleep(segundos)

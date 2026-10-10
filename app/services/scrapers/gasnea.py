"""Fuente FÁCIL 1: GasNea PDF directo (sin login ni CAPTCHA).

URL: https://www.gasnea.com.ar/descargas/matriculados_habilitados.pdf
Formato: localidades con filas NOMBRE ... MATRICULA ... CATEGORIA VENCIMIENTO.
Vencimiento típico 31/3/2027, categorías M1/M3 -> Primera/Segunda/Tercera.
"""

from __future__ import annotations

import io
import re
from datetime import date, datetime

from pypdf import PdfReader

from app.services.scrapers.base import FilaPadronExterna, fetch_bytes, sha256_bytes

URL_DEFAULT = "https://www.gasnea.com.ar/descargas/matriculados_habilitados.pdf"

FECHA_RE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
# Matrícula GasNea: 3-4 dígitos en los ejemplos vistos (579, 716, 3167...).
MAT_RE = re.compile(r"\b(\d{3,6})\b")
MAIL_RE = re.compile(r"\S+@\S+")


def _categoria_desde_token(token: str) -> str:
    t = token.strip().upper()
    if t in ("M1", "1", "PRIMERA"):
        return "Primera"
    if t in ("M2", "2", "SEGUNDA"):
        return "Segunda"
    if t in ("M3", "3", "TERCERA"):
        return "Tercera"
    if "PRIMERA" in t:
        return "Primera"
    if "SEGUNDA" in t:
        return "Segunda"
    if "TERCERA" in t:
        return "Tercera"
    return token.strip() or "Primera"


def parsear_pdf_bytes(data: bytes, fuente: str = URL_DEFAULT) -> tuple[list[FilaPadronExterna], dict]:
    reader = PdfReader(io.BytesIO(data))
    filas: list[FilaPadronExterna] = []
    rechazadas = 0
    for page in reader.pages:
        texto = page.extract_text() or ""
        for linea in texto.splitlines():
            linea = linea.strip()
            if not linea or "MATRICULADOS HABILITADOS" in linea.upper():
                continue
            fecha_m = FECHA_RE.search(linea)
            if not fecha_m:
                continue
            # Saca email para no confundir números del teléfono con matrícula.
            sin_mail = MAIL_RE.sub(" ", linea)
            # La matrícula suele ir justo antes de M1/M2/M3.
            m_cat = re.search(r"(\d{3,6})\s+(M[123])\b", sin_mail)
            if not m_cat:
                # Fallback: último número antes de la fecha.
                antes_fecha = sin_mail[: fecha_m.start()]
                nums = MAT_RE.findall(antes_fecha)
                if not nums:
                    rechazadas += 1
                    continue
                numero = nums[-1]
                cat_tok = "M1"
            else:
                numero = m_cat.group(1)
                cat_tok = m_cat.group(2)
            # Nombre: todo lo previo al CUIT (20.../27.../23...) o al primer teléfono.
            nombre = re.split(r"\b[23]\d{9,10}\b|\b\d{4,5}-\d{6,8}\b|\b\d{7,10}\b", linea, maxsplit=1)[0]
            nombre = re.sub(r"^[A-ZÁÉÍÓÚÑ\s]+?(?=[A-ZÁÉÍÓÚÑ]{3,})", "", nombre).strip(" ,-|")
            # Limpia localidad inicial en mayúsculas si viene pegada.
            nombre = nombre.strip()
            if not nombre or not numero.isdigit():
                rechazadas += 1
                continue
            try:
                venc = datetime.strptime(fecha_m.group(0), "%d/%m/%Y").date()
                if len(fecha_m.group(0).split("/")[0]) == 1:
                    venc = datetime.strptime(fecha_m.group(0), "%d/%m/%Y").date()
            except ValueError:
                rechazadas += 1
                continue
            filas.append(
                FilaPadronExterna(
                    tipo_profesional="Gasista",
                    numero_matricula=numero,
                    nombre_matriculado=nombre.upper()[:200],
                    categoria=_categoria_desde_token(cat_tok),
                    fecha_vencimiento=venc,
                    fuente=fuente,
                )
            )
    # Dedup por (tipo, numero): última gana.
    unicas: dict[str, FilaPadronExterna] = {}
    for f in filas:
        unicas[f.numero_matricula] = f
    return list(unicas.values()), {"paginas": len(reader.pages), "rechazadas": rechazadas, "hash": sha256_bytes(data)}


def scrapear(url: str = URL_DEFAULT) -> tuple[list[FilaPadronExterna], dict]:
    data = fetch_bytes(url)
    filas, info = parsear_pdf_bytes(data, fuente=url)
    info["bytes"] = len(data)
    info["fuente"] = url
    return filas, info

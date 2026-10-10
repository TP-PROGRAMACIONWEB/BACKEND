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
# Matrícula GasNea: 2-6 dígitos justo antes de M1/M2/M3, que viene pegado a
# la fecha sin espacio: "2991 M231/3/2027" = matrícula 2991, M2, 31/3/2027.
MAT_ANCORADA_RE = re.compile(r"\b(\d{2,6})\s+M([123])\s*\d")
CUIT_RE = re.compile(r"\b[23]\d{9,10}\b")
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
            # La matrícula va justo antes de M1/M2/M3 (que viene pegado a la
            # fecha: "M231/3/2027"). Sin esa ancla NO se acepta la fila: así se
            # evita agarrar años (2027) o códigos postales (3260, 3400).
            m_cat = MAT_ANCORADA_RE.search(sin_mail)
            if not m_cat:
                rechazadas += 1
                continue
            numero = m_cat.group(1)
            cat_tok = "M" + m_cat.group(2)
            # Nombre: lo que está entre el inicio y el CUIT (11 dígitos).
            # Incluye la localidad al inicio ("ALDEA PROTESTANTE WOLF, JULIO"):
            # no se recorta porque el match de HU-02 es por tokens y los
            # tokens del perfil igual encuentran su par.
            pre_cuit = CUIT_RE.split(linea, maxsplit=1)[0]
            nombre = re.sub(r"\s+", " ", pre_cuit).strip(" ,-|")
            if not nombre or not numero.isdigit():
                rechazadas += 1
                continue
            try:
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

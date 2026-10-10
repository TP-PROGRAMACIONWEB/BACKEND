"""Fuente FÁCIL 2: CACAAV listado HTML paginado (aire acondicionado).

URL: https://www.cacaav.com.ar/matriculados/listado?page=N
Filtros GET: apellido, nombre, empresa, provincia (id), localidad, inverter/rm.
Sin login ni CAPTCHA. ~33.000 instaladores. Ritmo 1 req / 2s.

Cada tarjeta trae: Nombre Apellido, dirección, teléfono, Vto: YYYY-MM-DD,
certificaciones (INVERTER / R410A / R32). La matrícula no viene como número
DNI en esta vista: se usa el nombre + localidad como identidad y se genera
numero interno estable? NO: para Offix se guarda numero = hash corto? NO.

Decisión: CACAAV no expone número DNI en el listado (solo nombre+contacto).
Para el padrón Offix (que valida por numero exacto 8 dígitos) esta fuente
sirve como detección de altas/bajas por nombre, y como complemento, no como
reemplazo del JSON actual. Se guarda numero_matricula = "" y se reporta como
pendiente de número oficial. El pipeline las cuenta como observadas.
Si el cliente provee el export con DNI, ese es el que manda.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from bs4 import BeautifulSoup

from app.services.scrapers.base import FilaPadronExterna, dormir_cortesia, fetch_texto

URL_BASE = "https://www.cacaav.com.ar/matriculados/listado"
VTO_RE = re.compile(r"Vto:[^0-9]*(\d{4}-\d{2}-\d{2})")


def parsear_pagina(html: str, fuente: str = URL_BASE) -> list[FilaPadronExterna]:
    soup = BeautifulSoup(html, "html.parser")
    filas: list[FilaPadronExterna] = []
    for card in soup.select("div.Tarjeta"):
        txt = card.get_text(" | ", strip=True)
        m = VTO_RE.search(txt)
        if not m:
            continue
        try:
            venc = datetime.strptime(m.group(1), "%Y-%m-%d").date()
        except ValueError:
            venc = date(2099, 12, 31)
        partes = [p.strip() for p in txt.split("|") if p.strip()]
        # Formato: [email?, Nombre, Empresa, Dirección, Teléfono, Vto:, fecha, certs...]
        nombre = ""
        for p in partes:
            if "@" in p or p.startswith("Vto") or re.match(r"^\d{4}-\d{2}-\d{2}$", p) or p.upper() in ("INVERTER", "R410A", "R32", "M.R410A"):
                continue
            if re.search(r"\d{3,}", p) and "," in p:
                continue  # dirección
            if re.match(r"^[\d\-\+\s\(\)]{7,}$", p):
                continue  # teléfono
            if len(p) < 4 or p.startswith("Instalador"):
                if p.startswith("Instalador"):
                    continue
            nombre = p
            break
        nombre = re.sub(r"\s+", " ", nombre).strip().upper()[:200]
        if not nombre or "MATRICUL" in nombre:
            continue
        filas.append(
            FilaPadronExterna(
                tipo_profesional="Aire acondicionado",
                numero_matricula="",  # sin DNI en esta vista
                nombre_matriculado=nombre,
                categoria="Sin categorizar",
                fecha_vencimiento=venc,
                fuente=fuente,
            )
        )
    return filas


def scrapear(paginas: int = 3, provincia: str = "", cortesia_seg: float = 2.0) -> tuple[list[FilaPadronExterna], dict]:
    todas: list[FilaPadronExterna] = []
    for p in range(paginas):
        params = {}
        if p:
            params["page"] = str(p)
        if provincia:
            params["provincia"] = provincia
        html = fetch_texto(URL_BASE, params=params or None)
        todas.extend(parsear_pagina(html, fuente=URL_BASE + (f"?page={p}" if p else "")))
        dormir_cortesia(cortesia_seg)
    return todas, {"paginas_visitadas": paginas, "observadas": len(todas), "fuente": URL_BASE}

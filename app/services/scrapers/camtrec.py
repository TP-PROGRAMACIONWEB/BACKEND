"""Fuente FÁCIL 3: CAMTREC listado + credencial (aire / refrigeración).

URLs:
- https://camtrec.org/matriculados?page=N  (208+ profesionales, 11 páginas)
- https://camtrec.org/c/<uuid>  (credencial con MAT-XXXXX, vigencia, especialidad)

Sin login para el listado. La credencial trae matrícula formato MAT-XXXXX
(distinto al DNI de 8 dígitos del padrón actual): se guarda como
numero_matricula = código MAT sin guion para no chocar con DNI, y el pipeline
la trata como fuente complementaria.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from app.services.scrapers.base import FilaPadronExterna, dormir_cortesia, fetch_texto

URL_BASE = "https://camtrec.org/matriculados"
MAT_RE = re.compile(r"MAT-([A-Z0-9]{4,8})")


def parsear_listado(html: str, fuente: str = URL_BASE) -> list[FilaPadronExterna]:
    soup = BeautifulSoup(html, "html.parser")
    filas: list[FilaPadronExterna] = []
    for card in soup.get_text("\n").split("Técnico Matriculado"):
        m = MAT_RE.search(card)
        if not m:
            continue
        lineas = [l.strip() for l in card.splitlines() if l.strip()]
        nombre = lineas[0] if lineas else ""
        nombre = re.sub(r"\s+", " ", nombre).strip().upper()[:200]
        if not nombre or "BUSC" in nombre:
            continue
        filas.append(
            FilaPadronExterna(
                tipo_profesional="Aire acondicionado",
                numero_matricula="MAT" + m.group(1),
                nombre_matriculado=nombre,
                categoria="Refrigeración/Climatización",
                fecha_vencimiento=__import__("datetime").date(2099, 12, 31),
                fuente=fuente,
            )
        )
    return filas


def scrapear(paginas: int = 3, cortesia_seg: float = 2.0) -> tuple[list[FilaPadronExterna], dict]:
    todas: list[FilaPadronExterna] = []
    for p in range(1, paginas + 1):
        url = URL_BASE if p == 1 else f"{URL_BASE}?page={p}"
        html = fetch_texto(url)
        todas.extend(parsear_listado(html, fuente=url))
        dormir_cortesia(cortesia_seg)
    # Dedup por numero.
    unicas = {}
    for f in todas:
        unicas[f.numero_matricula] = f
    return list(unicas.values()), {"paginas_visitadas": paginas, "observadas": len(unicas), "fuente": URL_BASE}

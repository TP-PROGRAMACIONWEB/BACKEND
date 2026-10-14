"""Fuente DIFÍCIL 1: Ecogas buscador Provincia/Localidad (el primero de los difíciles).

Página: https://www.ecogas.com.ar/hogares-comercios/tramites-y-servicios/listado-de-gasistas-matriculados
Comportamiento: Next.js client-side. Sin provincia+localidad+BUSCAR no hay
resultados en el HTML inicial. La tabla tiene columnas:
nombre/categoria/provincia/localidad/correo/telefono (+matrícula según vista).

Estrategia:
1. Intento con Playwright (headless): elige Provincia, Localidad, clic BUSCAR,
   recorre paginación y extrae filas. Es lo único robusto porque el sitio
   renderiza por JS y puede cambiar el endpoint interno sin aviso.
2. Si no hay Playwright instalado o el sitio cambia, fallback: export manual
   (guardar HTML resultante y parsearlo con parsear_html_guardado()).

Ritmo: 1 búsqueda por localidad, pausa 3s entre páginas. Nunca paralelo.
"""

from __future__ import annotations

import re
from datetime import date

from bs4 import BeautifulSoup

from app.services.scrapers.base import FilaPadronExterna

URL = "https://www.ecogas.com.ar/hogares-comercios/tramites-y-servicios/listado-de-gasistas-matriculados"


def _categoria_desde_token(token: str) -> str:
    t = token.strip().upper()
    return {"1": "Primera", "M1": "Primera", "2": "Segunda", "M2": "Segunda", "3": "Tercera", "M3": "Tercera"}.get(t, token.strip() or "Primera")


def parsear_html_guardado(html: str, fuente: str = URL) -> list[FilaPadronExterna]:
    """Parsea la tabla de Ecogas por columnas (TH): N° Matrícula | Nombre y
    Apellido | Categoría (1/2/3) | Provincia | Localidad | Correo | Teléfono."""
    soup = BeautifulSoup(html, "html.parser")
    filas: list[FilaPadronExterna] = []
    for tabla in soup.find_all("table"):
        ths = [th.get_text(" ", strip=True).upper() for th in tabla.find_all("th")]
        if not any("MATR" in h for h in ths):
            continue
        idx_mat = next((i for i, h in enumerate(ths) if "MATR" in h), 0)
        idx_nom = next((i for i, h in enumerate(ths) if "NOMBRE" in h), 1)
        idx_cat = next((i for i, h in enumerate(ths) if "CATEGOR" in h), 2)
        for tr in tabla.find_all("tr"):
            tds = [c.get_text(" ", strip=True) for c in tr.find_all("td")]
            if len(tds) <= max(idx_mat, idx_nom, idx_cat):
                continue
            numero = re.sub(r"\D", "", tds[idx_mat])
            nombre = re.sub(r"\s+", " ", tds[idx_nom]).strip().upper()[:200]
            if not numero or not nombre:
                continue
            filas.append(
                FilaPadronExterna(
                    tipo_profesional="Gasista",
                    numero_matricula=numero,
                    nombre_matriculado=nombre,
                    categoria=_categoria_desde_token(tds[idx_cat]),
                    fecha_vencimiento=date(2027, 3, 31),
                    fuente=fuente,
                )
            )
    unicas = {}
    for f in filas:
        unicas[(f.tipo_profesional, f.numero_matricula)] = f
    return list(unicas.values())


def scrapear(provincia: str = "Córdoba", localidad: str = "San Francisco", max_paginas: int = 10) -> tuple[list[FilaPadronExterna], dict]:
    """Automatización con Playwright. Requiere: pip install playwright + playwright install chromium."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        return [], {
            "ok": False,
            "error": "Falta playwright. Instalá con: pip install playwright; playwright install chromium. Alternativa: guardá el HTML con resultados y usá parsear_html_guardado().",
            "fuente": URL,
        }
    filas: list[FilaPadronExterna] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(user_agent="OffixBot/1.0 (UTN-FRSF academico)")
        page.goto(URL, wait_until="networkidle", timeout=45000)
        # Selectores tolerantes (el sitio usa custom selects con buttons).
        try:
            # Provincia: click en el header del custom select y elegir opción por texto.
            page.get_by_text("Seleccioná una provincia", exact=False).first.click(timeout=10000)
            page.get_by_text(provincia, exact=False).first.click(timeout=10000)
            page.wait_for_timeout(1500)
            # Localidad similar si se pasa.
            if localidad:
                try:
                    page.get_by_text("Seleccioná una localidad", exact=False).first.click(timeout=8000)
                    page.get_by_text(localidad, exact=False).first.click(timeout=8000)
                    page.wait_for_timeout(1500)
                except Exception:
                    pass
            # Botón BUSCAR.
            page.get_by_role("button", name=re.compile("BUSCAR", re.I)).click(timeout=10000)
            page.wait_for_timeout(4000)
        except Exception as e:
            browser.close()
            return [], {"ok": False, "error": f"No se pudo operar el buscador (el sitio cambió?): {e}", "fuente": URL}
        for _ in range(max_paginas):
            html = page.content()
            filas.extend(parsear_html_guardado(html, fuente=URL))
            # Siguiente página si existe.
            try:
                btn = page.get_by_role("button", name=re.compile("Siguiente|>", re.I)).first
                if not btn.is_visible() or btn.is_disabled():
                    break
                btn.click(timeout=5000)
                page.wait_for_timeout(3000)
            except Exception:
                break
        browser.close()
    unicas = {}
    for f in filas:
        unicas[(f.tipo_profesional, f.numero_matricula)] = f
    return list(unicas.values()), {"ok": True, "paginas": max_paginas, "total": len(unicas), "fuente": URL,
                                   "provincia": provincia, "localidad": localidad}

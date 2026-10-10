"""Endpoint para cron-job.org (no usa JWT, usa CRON_SECRET).

cron-job.org solo hace requests HTTP programados, no ejecuta Python.
Por eso se expone este endpoint: cron-job.org lo llama 1 vez por mes y
el backend ejecuta el sync liviano (archivos locales + GasNea/CACAAV con
límite de páginas para no exceder el timeout serverless).

Config en cron-job.org:
- URL: https://backend-offix3.vercel.app/api/v1/cron/padrones/sync?secret=TU_SECRETO&fuente=local&dry_run=false
- Método: GET o POST. Frecuencia: mensual día 1 00:00 ART.
- Secret: el mismo valor de la env CRON_SECRET en Vercel.

Fuentes: local | gasnea | cacaav | camtrec | ecogas | todas
"""

import secrets
import traceback

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.services import padrones_sync
from app.services.scrapers import cacaav, camtrec, gasnea

router = APIRouter(prefix="/api/v1/cron/padrones", tags=["Cron Padrones"])


def _check_secret(secret: str):
    esperado = getattr(settings, "cron_secret", "")
    if not esperado or not secrets.compare_digest(secret, esperado):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Cron secret inválido")


@router.get("/sync", summary="Sync de padrones para cron-job.org")
@router.post("/sync", summary="Sync de padrones para cron-job.org")
def sync(
    secret: str = Query(..., description="Igual a CRON_SECRET en Vercel"),
    fuente: str = Query("local", description="local|gasnea|cacaav|camtrec|ecogas|todas"),
    dry_run: bool = Query(True, description="True = solo reporte, no escribe"),
    paginas: int = Query(1, ge=1, le=5, description="Páginas por scraper web (límite serverless)"),
    db: Session = Depends(get_db),
):
    _check_secret(secret)
    filas = []
    detalle: dict = {}
    # Cada fuente aislada: si una cae, las demás igual se procesan.
    # En serverless no hay pausas de cortesía (timeout de 10s en Hobby).
    try:
        if fuente in ("local", "todas"):
            n_antes = len(filas)
            filas += padrones_sync.filas_desde_archivos_locales()
            detalle["local"] = {"filas": len(filas) - n_antes}
    except Exception as ex:
        detalle["local"] = {"error": f"{type(ex).__name__}: {ex}"}
    try:
        if fuente in ("gasnea", "todas"):
            g, info = gasnea.scrapear()
            validas = [f for f in g if f.numero_matricula.isdigit()]
            filas += validas
            detalle["gasnea"] = {**info, "validas": len(validas)}
    except Exception as ex:
        detalle["gasnea"] = {"error": f"{type(ex).__name__}: {ex}"}
    try:
        if fuente in ("cacaav", "todas"):
            c, info = cacaav.scrapear(paginas=paginas, cortesia_seg=0)
            detalle["cacaav"] = info  # observadas (sin DNI en vista)
    except Exception as ex:
        detalle["cacaav"] = {"error": f"{type(ex).__name__}: {ex}"}
    try:
        if fuente in ("camtrec", "todas"):
            m, info = camtrec.scrapear(paginas=paginas, cortesia_seg=0)
            filas += m
            detalle["camtrec"] = {**info, "sumadas": len(m)}
    except Exception as ex:
        detalle["camtrec"] = {"error": f"{type(ex).__name__}: {ex}"}
    if fuente in ("ecogas",):
        # Ecogas necesita navegador (Playwright): no corre en serverless.
        detalle["ecogas"] = {"error": "Ecogas requiere Playwright: correr con CLI local (python -m app.scripts.actualizar_padron --fuente ecogas)"}
    try:
        reporte = padrones_sync.sincronizar(db, filas, origen=f"cron:{fuente}", dry_run=dry_run)
    except Exception:
        raise HTTPException(status_code=500, detail=f"Falla al guardar en BD: {traceback.format_exc(limit=3)}")
    reporte["detalle"] = detalle
    return reporte


@router.get("/health", summary="Chequeo cron")
def cron_health():
    return {"status": "ok", "uso": "cron-job.org -> GET /api/v1/cron/padrones/sync?secret=...&fuente=local&dry_run=true"}

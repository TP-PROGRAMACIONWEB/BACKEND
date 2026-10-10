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

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.services import padrones_sync
from app.services.scrapers import cacaav, camtrec, ecogas, gasnea

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
    paginas: int = Query(2, ge=1, le=5, description="Páginas por scraper web (límite serverless)"),
    db: Session = Depends(get_db),
):
    _check_secret(secret)
    filas = []
    detalle: dict = {}
    try:
        if fuente in ("local", "todas"):
            filas += padrones_sync.filas_desde_archivos_locales()
            detalle["local"] = len(filas)
        if fuente in ("gasnea", "todas"):
            g, info = gasnea.scrapear()
            filas += [f for f in g if f.numero_matricula.isdigit()]
            detalle["gasnea"] = info
        if fuente in ("cacaav", "todas"):
            c, info = cacaav.scrapear(paginas=paginas)
            detalle["cacaav"] = info  # observadas (sin DNI en vista)
        if fuente in ("camtrec", "todas"):
            m, info = camtrec.scrapear(paginas=paginas)
            filas += m
            detalle["camtrec"] = info
        if fuente in ("ecogas",):
            e, info = ecogas.scrapear()
            filas += e
            detalle["ecogas"] = info
    except Exception as ex:
        raise HTTPException(status_code=502, detail=f"Falla al extraer: {ex}")
    reporte = padrones_sync.sincronizar(db, filas, origen=f"cron:{fuente}", dry_run=dry_run)
    reporte["detalle"] = {k: (v if isinstance(v, dict) else v) for k, v in detalle.items()}
    return reporte


@router.get("/health", summary="Chequeo cron")
def cron_health():
    return {"status": "ok", "uso": "cron-job.org -> GET /api/v1/cron/padrones/sync?secret=...&fuente=local&dry_run=true"}

"""CLI: python -m app.scripts.actualizar_padron --fuente local|gasnea|cacaav|camtrec|ecogas|todas [--dry-run] [--confirm] [--paginas 2] [--incluir-ecogas]

--dry-run: solo reporte, no escribe. Escritura real exige --confirm.
Cada fuente va aislada: si una cae (red, HTML cambiado), las demás igual se
procesan y el error queda en el reporte. `ecogas` necesita Playwright y solo
entra en `todas` con --incluir-ecogas (en GitHub Actions sí está instalado).
"""

import argparse
import sys
import traceback

from app.db.database import SessionLocal, preparar_esquema
from app.models import (  # noqa: F401 - registra mappers para create_all
    alerta_admin,
    archivo_adjunto,
    categoria,
    emision_resena,
    matricula,
    notificacion,
    oferente,
    oferente_dia_atencion,
    resena,
    solicitud_resena,
    trabajo_realizado,
    usuario,
)
from app.services import padrones_sync
from app.services.scrapers import cacaav, camtrec, ecogas, gasnea


def parse_args():
    p = argparse.ArgumentParser(description="Actualiza padron_matriculas desde archivos o web")
    p.add_argument("--fuente", default="local", choices=["local", "gasnea", "cacaav", "camtrec", "ecogas", "todas"])
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--confirm", action="store_true")
    p.add_argument("--paginas", type=int, default=2)
    p.add_argument("--provincia", default="Córdoba")
    p.add_argument("--localidad", default="San Francisco")
    p.add_argument("--incluir-ecogas", action="store_true", help="Incluye Ecogas en fuente=todas (requiere Playwright)")
    return p.parse_args()


def _intentar(nombre: str, fn):
    try:
        return fn()
    except Exception as ex:
        print(f"{nombre}: FALLA ({type(ex).__name__}: {ex}). Se sigue con las demás fuentes.")
        traceback.print_exc(limit=2)
        return []


def recolectar(fuente: str, paginas: int, provincia: str, localidad: str, incluir_ecogas: bool = False):
    filas = []
    if fuente in ("local", "todas"):
        filas += padrones_sync.filas_desde_archivos_locales()
        print(f"local: {len(filas)} filas de archivos")
    if fuente in ("gasnea", "todas"):
        def _gasnea():
            g, info = gasnea.scrapear()
            print(f"gasnea: {len(g)} filas, hash={info.get('hash', '')[:12]}")
            return [f for f in g if f.numero_matricula.isdigit()]
        filas += _intentar("gasnea", _gasnea)
    if fuente in ("cacaav", "todas"):
        def _cacaav():
            c, info = cacaav.scrapear(paginas=paginas)
            print(f"cacaav: observadas={info.get('observadas')} (sin DNI en vista, no se insertan)")
            return []
        filas += _intentar("cacaav", _cacaav)
    if fuente in ("camtrec", "todas"):
        def _camtrec():
            m, info = camtrec.scrapear(paginas=paginas)
            print(f"camtrec: {len(m)} filas, {info}")
            return m
        filas += _intentar("camtrec", _camtrec)
    if fuente in ("ecogas",) or (fuente == "todas" and incluir_ecogas):
        def _ecogas():
            e, info = ecogas.scrapear(provincia=provincia, localidad=localidad)
            print(f"ecogas: {len(e)} filas")
            return e
        filas += _intentar("ecogas", _ecogas)
    return filas


def main():
    a = parse_args()
    filas = recolectar(a.fuente, a.paginas, a.provincia, a.localidad, a.incluir_ecogas)
    print(f"Total candidatas: {len(filas)}")
    if a.dry_run or not a.confirm:
        if not a.confirm:
            print("Modo seguro: sin --confirm no se escribe. Agregá --confirm para aplicar o --dry-run para ver.")
        preparar_esquema()
        db = SessionLocal()
        try:
            rep = padrones_sync.sincronizar(db, filas, origen=f"cli:{a.fuente}", dry_run=True)
        finally:
            db.close()
        print(f"DRY-RUN: insertadas={rep['insertadas']} actualizadas={rep['actualizadas']} intactas={rep['intactas']} rechazadas={len(rep['rechazadas'])}")
        for r in rep["rechazadas"][:10]:
            print("  rech:", r)
        if not a.confirm:
            sys.exit(2)
        return
    preparar_esquema()
    db = SessionLocal()
    try:
        rep = padrones_sync.sincronizar(db, filas, origen=f"cli:{a.fuente}", dry_run=False)
        print(f"OK: insertadas={rep['insertadas']} actualizadas={rep['actualizadas']} intactas={rep['intactas']} rechazadas={len(rep['rechazadas'])}")
    except Exception as e:
        db.rollback()
        print(f"FALLO: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()

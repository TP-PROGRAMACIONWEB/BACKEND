"""CLI: python -m app.scripts.actualizar_padron --fuente local|gasnea|cacaav|camtrec|ecogas|todas [--dry-run] [--confirm] [--paginas 2]

--dry-run: solo reporte, no escribe. Escritura real exige --confirm.
"""

import argparse
import sys

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
    return p.parse_args()


def recolectar(fuente: str, paginas: int, provincia: str, localidad: str):
    filas = []
    if fuente in ("local", "todas"):
        filas += padrones_sync.filas_desde_archivos_locales()
        print(f"local: {len(filas)} filas de archivos")
    if fuente in ("gasnea", "todas"):
        g, info = gasnea.scrapear()
        print(f"gasnea: {len(g)} filas, {info}")
        filas += [f for f in g if f.numero_matricula.isdigit()]
    if fuente in ("cacaav", "todas"):
        c, info = cacaav.scrapear(paginas=paginas)
        print(f"cacaav: observadas={info} (sin DNI en vista, no se insertan)")
    if fuente in ("camtrec", "todas"):
        m, info = camtrec.scrapear(paginas=paginas)
        print(f"camtrec: {len(m)} filas, {info}")
        filas += m
    if fuente in ("ecogas", "todas"):
        e, info = ecogas.scrapear(provincia=provincia, localidad=localidad)
        print(f"ecogas: {len(e)} filas, {info}")
        filas += e
    return filas


def main():
    a = parse_args()
    filas = recolectar(a.fuente, a.paginas, a.provincia, a.localidad)
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

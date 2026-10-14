"""Carga padrones a Supabase por REST (sin password de BD).

Usa la service_role vía PostgREST: sirve en GitHub Actions sin exponer la
database password. Requiere que el schema `offix` esté expuesto en Data API
y los grants de escritura (ver docs del workflow).

Uso:
  SUPABASE_URL=https://<ref>.supabase.co SUPABASE_SERVICE_ROLE=<jwt> \
    python -m app.scripts.cargar_padron_rest --fuente todas --incluir-ecogas --confirm

--dry-run: solo cuenta candidatas, no escribe.
"""

import argparse
import os
import sys

import httpx

from app.services.padrones_sync import filas_desde_archivos_locales
from app.services.scrapers.base import normalizar_texto


def parse_args():
    p = argparse.ArgumentParser(description="Carga padrones a Supabase por REST")
    p.add_argument("--fuente", default="local", choices=["local", "gasnea", "cacaav", "camtrec", "ecogas", "todas"])
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--confirm", action="store_true")
    p.add_argument("--paginas", type=int, default=2)
    p.add_argument("--provincia", default="Córdoba")
    p.add_argument("--localidad", default="San Francisco")
    p.add_argument("--incluir-ecogas", action="store_true")
    return p.parse_args()


def recolectar(fuente, paginas, provincia, localidad, incluir_ecogas):
    from app.services.scrapers import cacaav, camtrec, ecogas, gasnea

    filas = []
    if fuente in ("local", "todas"):
        filas += filas_desde_archivos_locales()
    if fuente in ("gasnea", "todas"):
        try:
            g, _ = gasnea.scrapear()
            filas += [f for f in g if f.numero_matricula.isdigit()]
        except Exception as ex:
            print(f"gasnea: FALLA ({ex}), se sigue.")
    if fuente in ("camtrec", "todas"):
        try:
            m, _ = camtrec.scrapear(paginas=paginas)
            filas += m
        except Exception as ex:
            print(f"camtrec: FALLA ({ex}), se sigue.")
    if fuente in ("ecogas",) or (fuente == "todas" and incluir_ecogas):
        try:
            e, _ = ecogas.scrapear(provincia=provincia, localidad=localidad)
            filas += e
        except Exception as ex:
            print(f"ecogas: FALLA ({ex}), se sigue.")
    return filas


def main():
    a = parse_args()
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE", "")
    if not url or not key:
        print("Faltan SUPABASE_URL y/o SUPABASE_SERVICE_ROLE en el entorno.")
        sys.exit(2)
    filas = recolectar(a.fuente, a.paginas, a.provincia, a.localidad, a.incluir_ecogas)
    print(f"candidatas: {len(filas)}")
    if a.dry_run or not a.confirm:
        print("DRY-RUN: no se escribe. Agregá --confirm para aplicar.")
        return
    h = {
        "apikey": key,
        "Authorization": "Bearer " + key,
        "Content-Profile": "offix",
        "Accept-Profile": "offix",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }
    rows = [
        {
            "tipo_profesional": f.tipo_profesional,
            "numero_matricula": f.numero_matricula,
            "nombre_matriculado": normalizar_texto(f.nombre_matriculado),
            "categoria": f.categoria,
            "fecha_vencimiento": f.fecha_vencimiento.isoformat(),
        }
        for f in filas
    ]
    with httpx.Client(timeout=30) as c:
        for i in range(0, len(rows), 50):
            r = c.post(url + "/rest/v1/padron_matriculas?on_conflict=tipo_profesional,numero_matricula", headers=h, json=rows[i : i + 50])
            print(f"lote {i}: {r.status_code}")
            if r.status_code not in (200, 201):
                print(r.text[:300])
                sys.exit(1)
        r = c.get(url + "/rest/v1/padron_matriculas?select=id_padron", headers={**h, "Prefer": "count=exact"}, timeout=30)
        print("total en BD:", r.headers.get("content-range"))


if __name__ == "__main__":
    main()

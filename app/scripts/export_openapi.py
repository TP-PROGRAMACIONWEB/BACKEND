"""Exporta el spec OpenAPI de la app a docs/openapi.json, para que el equipo lo
importe en Hoppscotch/Postman o lo comparta con el frontend sin necesidad de
tener el backend corriendo.

Uso: python -m app.scripts.export_openapi
"""

import json
from pathlib import Path

from app.main import app

OUTPUT_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "openapi.json"


def run():
    schema = app.openapi()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"OpenAPI spec exportado a {OUTPUT_PATH} ({len(schema['paths'])} endpoints).")


if __name__ == "__main__":
    run()

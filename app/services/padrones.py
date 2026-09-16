"""Parser de los padrones de matriculados (`app/db/padrones/*.md`).

Son tablas markdown exportadas de un PDF, con el encabezado malformado (viene
partido en varias celdas y con etiquetas HTML sueltas). Por eso se parsea
**por posición**, no por nombre de columna: la matrícula siempre está en la
posición 3, sea cual sea el estado del resto de la fila.

Ver `docs/plan-sprint-1.md`, sección "Padrón de matriculados", para el
detalle del formato y de las filas sucias del export.
"""

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

CATEGORIA_RE = re.compile(r"Primera|Segunda|Tercera")
FECHA_RE = re.compile(r"\d{2}/\d{2}/\d{4}")


@dataclass
class FilaPadron:
    nombre_matriculado: str
    numero_matricula: str
    categoria: str
    fecha_vencimiento: date


def _es_fila_de_datos(columnas: list[str]) -> bool:
    """La matrícula (posición 3) es la única columna que ninguna fila sucia
    del export llega a romper. El encabezado (`MATRÍCULA`) y el separador
    (`---`) no son numéricos, así que quedan afuera sin necesidad de una
    lista de exclusiones."""
    return len(columnas) >= 6 and columnas[3].strip().isdigit()


def parsear_padron_md(path: Path) -> list[FilaPadron]:
    filas: list[FilaPadron] = []
    texto = Path(path).read_text(encoding="utf-8")

    for linea in texto.splitlines():
        linea = linea.strip()
        if not linea.startswith("|"):
            continue

        columnas = [celda.strip() for celda in linea.strip("|").split("|")]
        if not _es_fila_de_datos(columnas):
            continue

        categoria_match = CATEGORIA_RE.search(columnas[4])
        fecha_match = FECHA_RE.search(columnas[5])
        if not categoria_match or not fecha_match:
            continue

        filas.append(
            FilaPadron(
                nombre_matriculado=columnas[0],
                numero_matricula=columnas[3],
                categoria=categoria_match.group(0),
                fecha_vencimiento=datetime.strptime(fecha_match.group(0), "%d/%m/%Y").date(),
            )
        )

    return filas

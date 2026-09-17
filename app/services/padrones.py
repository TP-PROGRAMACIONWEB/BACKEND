"""Parser de los padrones de matriculados (`app/db/padrones/*`).

Dos formatos, uno por tipo de profesional:

- **Gasistas** (`gasistas.md`): tabla markdown exportada de un PDF, con el
  encabezado malformado (viene partido en varias celdas y con etiquetas HTML
  sueltas). Se parsea **por posición**, no por nombre de columna: la matrícula
  siempre está en la posición 3, sea cual sea el estado del resto de la fila.
- **Aire acondicionado** (`aire-acondicionado.json`): export JSON de otro
  sistema, con campos estructurados (`matricula`, `apellido`, `nombre`, ...).
  **Sin categoría ni vencimiento** — ver `PLACEHOLDER_*` más abajo — y
  **parcial**: 50 de los 77 matriculados totales (falta la página 2 del
  export). Ver `docs/plan-sprint-1.md`, pregunta abierta #1.

Ver `docs/plan-sprint-1.md`, sección "Padrón de matriculados", para el
detalle del formato y de las filas sucias del export de Gasistas.
"""

import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

CATEGORIA_RE = re.compile(r"Primera|Segunda|Tercera")
FECHA_RE = re.compile(r"\d{2}/\d{2}/\d{4}")

# El export de Aire acondicionado no trae categoría ni vencimiento (a
# diferencia del de Gasistas). Sin esos datos no hay padrón real que cargar,
# así que se usa un placeholder explícito hasta que llegue el dato real:
# ninguno de estos matriculados puede dar "Vencida" con esto cargado.
PLACEHOLDER_CATEGORIA = "Sin categorizar"
PLACEHOLDER_VENCIMIENTO = date(2099, 12, 31)

# Longitud real de la matrícula de Aire acondicionado (confirmada con el
# export real: 8 dígitos, no los 9 que asumía el CA01). Cualquier fila que no
# la respete es ruido del export, no un matriculado real — mismo criterio que
# usa `_es_fila_de_datos` para Gasistas.
DIGITOS_AIRE_ACONDICIONADO = 8


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


def parsear_padron_json(path: Path) -> list[FilaPadron]:
    """Export estructurado (Aire acondicionado). Cada registro trae
    `apellido`, `nombre` y `matricula` sueltos: se arma `nombre_matriculado`
    como "APELLIDO NOMBRE" para que quede en el mismo formato que usa el
    algoritmo de coincidencia de nombre (`comparar_nombres` normaliza mayúsculas
    y acentos igual para los dos padrones, así que el orden no afecta el
    resultado, pero mantenerlo consistente ayuda a leer la tabla)."""
    datos = json.loads(Path(path).read_text(encoding="utf-8"))

    filas: list[FilaPadron] = []
    for registro in datos["data"]:
        numero = registro["matricula"].strip()
        # Filtra el ruido del export: cualquier matrícula que no tenga la
        # longitud real (8 dígitos) no es un matriculado válido — es el caso
        # de la fila duplicada de prueba que trae este export ("111111111").
        if not numero.isdigit() or len(numero) != DIGITOS_AIRE_ACONDICIONADO:
            continue

        filas.append(
            FilaPadron(
                nombre_matriculado=f"{registro['apellido']} {registro['nombre']}".strip().upper(),
                numero_matricula=numero,
                categoria=PLACEHOLDER_CATEGORIA,
                fecha_vencimiento=PLACEHOLDER_VENCIMIENTO,
            )
        )

    return filas

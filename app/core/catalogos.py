"""Catálogos fijos del registro de Oferente (HU-04, D14 y D9).

Son constantes del código y no tablas: cambiarlos requiere una migración de
datos, así que no conviene que el DBA los edite a mano. El frontend los recibe
desde `GET /api/v1/catalogos/registro-oferente`.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RangoExperiencia:
    codigo: str
    etiqueta: str


EXPERIENCIA = (
    RangoExperiencia("MENOS_1", "Menos de 1 año (Inicial)"),
    RangoExperiencia("1_A_2", "1 a 2 años (Junior)"),
    RangoExperiencia("3_A_5", "3 a 5 años (Experimentado)"),
    RangoExperiencia("6_A_10", "6 a 10 años (Senior)"),
    RangoExperiencia("MAS_10", "Más de 10 años (Experto)"),
)

ETIQUETA_EXPERIENCIA = {rango.codigo: rango.etiqueta for rango in EXPERIENCIA}

# ISO-8601: 1 = Lunes ... 7 = Domingo.
DIAS = (
    (1, "Lun", "Lunes"),
    (2, "Mar", "Martes"),
    (3, "Mié", "Miércoles"),
    (4, "Jue", "Jueves"),
    (5, "Vie", "Viernes"),
    (6, "Sáb", "Sábado"),
    (7, "Dom", "Domingo"),
)

DIAS_VALIDOS = frozenset(dia for dia, _, _ in DIAS)

HORARIO_POR_DEFECTO = {"apertura": "08:00", "cierre": "18:00"}

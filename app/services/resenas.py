"""Reglas de reseña compartidas entre routers.

El recálculo del promedio lo disparan dos caminos —la moderación del Profesional
y la publicación forzada del Administrador (RF17)—, así que no puede vivir en
uno solo de los dos routers.
"""

from sqlalchemy.orm import Session

from app.models.oferente import Oferente
from app.models.resena import EstadoResena, Resena


def recalcular_promedio(db: Session, oferente: Oferente) -> None:
    """Promedio de las puntuaciones globales de las reseñas **aceptadas**, con
    dos decimales. Las pendientes y las rechazadas no suman; sin reseñas
    aceptadas, el promedio vuelve a 0."""
    aceptadas = (
        db.query(Resena).filter(Resena.oferente_id == oferente.id_oferente, Resena.estado == EstadoResena.ACEPTADA).all()
    )
    puntuaciones = [resena.calificaciones_comentarios["puntuacion_global"] for resena in aceptadas]
    oferente.promedio_calificacion = round(sum(puntuaciones) / len(puntuaciones), 2) if puntuaciones else 0

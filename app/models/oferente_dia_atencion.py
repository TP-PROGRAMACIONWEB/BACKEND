from sqlalchemy import CheckConstraint, Column, ForeignKey, Integer, SmallInteger
from sqlalchemy.orm import relationship

from app.db.database import Base


class OferenteDiaAtencion(Base):
    """Un día de la semana en el que el Oferente atiende (HU-04, D9).

    `dia` sigue ISO-8601: 1 = Lunes … 7 = Domingo. Tabla hija en vez de una
    máscara de bits, para poder consultarla y filtrarla desde SQL.
    """

    __tablename__ = "oferente_dias_atencion"
    __table_args__ = (CheckConstraint("dia BETWEEN 1 AND 7", name="ck_dia_atencion_rango"),)

    oferente_id = Column(Integer, ForeignKey("oferentes.id_oferente", ondelete="CASCADE"), primary_key=True)
    dia = Column(SmallInteger, primary_key=True)

    oferente = relationship("Oferente", back_populates="dias_atencion")

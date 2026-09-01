from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.database import Base


class EstadoCategoria:
    ACTIVA = "Activa"
    INACTIVA = "Inactiva"


class Categoria(Base):
    __tablename__ = "categorias"

    id_categoria = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False, unique=True)
    descripcion = Column(Text, nullable=True)
    estado = Column(String(50), nullable=False, default=EstadoCategoria.ACTIVA)

    oferentes = relationship("Oferente", back_populates="categoria")

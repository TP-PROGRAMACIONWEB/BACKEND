from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from app.db.database import Base


class ArchivoAdjunto(Base):
    __tablename__ = "archivos_adjuntos"

    id_archivo = Column(Integer, primary_key=True, index=True)
    oferente_id = Column(Integer, ForeignKey("oferentes.id_oferente"), nullable=False)
    tipo = Column(String(50), nullable=False)
    url_archivo = Column(String(255), nullable=False)
    fecha_subida = Column(DateTime(timezone=True), server_default=func.now())

    oferente = relationship("Oferente", back_populates="archivos")

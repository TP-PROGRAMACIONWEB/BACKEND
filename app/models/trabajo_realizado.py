from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.db.database import Base


class TrabajoRealizado(Base):
    """Un trabajo que el Oferente muestra en su perfil (HU-04 T06, D13).

    Las fotos viven en ARCHIVO_ADJUNTO con tipo Trabajo y trabajo_id apuntando
    acá. Borrar el trabajo borra sus filas (CASCADE); los objetos de Storage los
    borra el router antes, porque la base no los conoce.
    """

    __tablename__ = "trabajos_realizados"

    id_trabajo = Column(Integer, primary_key=True, index=True)
    oferente_id = Column(Integer, ForeignKey("oferentes.id_oferente", ondelete="CASCADE"), nullable=False, index=True)
    titulo = Column(String(100), nullable=False)
    descripcion = Column(Text, nullable=True)
    fecha_creacion = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    oferente = relationship("Oferente", back_populates="trabajos")
    fotos = relationship(
        "ArchivoAdjunto",
        back_populates="trabajo",
        cascade="all, delete-orphan",
        order_by="ArchivoAdjunto.orden",
    )

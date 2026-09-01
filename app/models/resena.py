from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.db.database import Base


class Resena(Base):
    __tablename__ = "resenas"

    id_resena = Column(Integer, primary_key=True, index=True)
    oferente_id = Column(Integer, ForeignKey("oferentes.id_oferente"), nullable=False)
    solicitud_id = Column(Integer, ForeignKey("solicitudes_resena.id_solicitud"), nullable=False)

    nombre_cliente = Column(String(100), nullable=False)
    contacto_cliente_ingresado = Column(String(100), nullable=False)
    calificacion = Column(Integer, nullable=False)
    comentario = Column(Text, nullable=True)
    estado = Column(String(50), nullable=False, default="pendiente")
    replica_oferente = Column(Text, nullable=True)
    fecha_creacion = Column(DateTime(timezone=True), server_default=func.now())

    oferente = relationship("Oferente", back_populates="resenas")
    solicitud = relationship("SolicitudResena", back_populates="resenas")

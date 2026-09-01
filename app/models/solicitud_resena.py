from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from app.db.database import Base


class SolicitudResena(Base):
    __tablename__ = "solicitudes_resena"

    id_solicitud = Column(Integer, primary_key=True, index=True)
    oferente_id = Column(Integer, ForeignKey("oferentes.id_oferente"), nullable=False)
    codigo_unico = Column(String(100), nullable=False, unique=True, index=True)
    contacto_referencia_cliente = Column(String(100), nullable=True)
    intentos_rechazo = Column(Integer, nullable=False, default=0)
    estado = Column(String(50), nullable=False, default="pendiente")
    fecha_generacion = Column(DateTime(timezone=True), server_default=func.now())
    fecha_expiracion = Column(DateTime(timezone=True), nullable=True)

    oferente = relationship("Oferente", back_populates="solicitudes_resena")
    resenas = relationship("Resena", back_populates="solicitud", cascade="all, delete-orphan")

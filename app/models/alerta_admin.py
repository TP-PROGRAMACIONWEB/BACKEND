from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.db.database import Base


class AlertaAdministrador(Base):
    __tablename__ = "alertas_administrador"

    id_alerta = Column(Integer, primary_key=True, index=True)
    oferente_id = Column(Integer, ForeignKey("oferentes.id_oferente"), nullable=False)
    motivo = Column(Text, nullable=False)
    estado_revision = Column(String(50), nullable=False, default="pendiente")
    fecha_creacion = Column(DateTime(timezone=True), server_default=func.now())

    oferente = relationship("Oferente", back_populates="alertas")

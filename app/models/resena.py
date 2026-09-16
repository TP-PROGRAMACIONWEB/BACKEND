from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from app.db.database import Base


class EstadoResena:
    """Vocabulario alineado con la UI y con los casos de prueba de QA: los
    botones de la bandeja dicen Aceptar / Rechazar, no Aprobar."""

    PENDIENTE_ACEPTACION = "Pendiente_Aceptacion"
    ACEPTADA = "Aceptada"
    RECHAZADA = "Rechazada"


class Resena(Base):
    __tablename__ = "resenas"

    id_resena = Column(Integer, primary_key=True, index=True)
    oferente_id = Column(Integer, ForeignKey("oferentes.id_oferente", ondelete="CASCADE"), nullable=False, index=True)
    solicitud_id = Column(Integer, ForeignKey("solicitudes_resena.id_solicitud", ondelete="CASCADE"), nullable=False)

    # Copiados de la solicitud al crear la reseña: el cliente ya no los tipea en
    # este paso, los ve precargados y bloqueados.
    nombre_cliente = Column(String(100), nullable=False)
    contacto_cliente_ingresado = Column(String(100), nullable=False)
    calificaciones_comentarios = Column(JSON, nullable=False)
    estado = Column(String(50), nullable=False, default=EstadoResena.PENDIENTE_ACEPTACION)
    fecha_creacion = Column(DateTime(timezone=True), server_default=func.now())

    oferente = relationship("Oferente", back_populates="resenas")
    solicitud = relationship("SolicitudResena", back_populates="resenas")
    notificaciones = relationship("Notificacion", back_populates="resena", cascade="all, delete-orphan")

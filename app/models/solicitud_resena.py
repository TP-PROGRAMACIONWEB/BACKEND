from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from app.db.database import Base


class EstadoSolicitud:
    PENDIENTE_USO = "Pendiente_Uso"
    UTILIZADA = "Utilizada"
    EXPIRADA = "Expirada"


class OrigenSolicitud:
    """Cómo se generó el enlace de reseña. Define si la vista muestra los datos
    del cliente bloqueados y si la reseña necesita verificarse por correo."""

    CLIENTE_EMAIL = "Cliente_Email"
    OFERENTE_WHATSAPP = "Oferente_WhatsApp"


class SolicitudResena(Base):
    __tablename__ = "solicitudes_resena"

    id_solicitud = Column(Integer, primary_key=True, index=True)
    oferente_id = Column(Integer, ForeignKey("oferentes.id_oferente", ondelete="CASCADE"), nullable=False, index=True)
    codigo_unico = Column(String(100), nullable=False, unique=True, index=True)

    # Nullables: el flujo por WhatsApp crea la solicitud en blanco y es el cliente
    # quien carga estos datos recién al completar la reseña.
    nombre_cliente = Column(String(100), nullable=True)
    email_cliente = Column(String(255), nullable=True)

    origen = Column(String(50), nullable=False, default=OrigenSolicitud.CLIENTE_EMAIL)
    estado = Column(String(50), nullable=False, default=EstadoSolicitud.PENDIENTE_USO)
    intentos_rechazo = Column(Integer, nullable=False, default=0)
    fecha_generacion = Column(DateTime(timezone=True), server_default=func.now())
    fecha_expiracion = Column(DateTime(timezone=True), nullable=True)

    oferente = relationship("Oferente", back_populates="solicitudes_resena")
    resenas = relationship("Resena", back_populates="solicitud", cascade="all, delete-orphan")

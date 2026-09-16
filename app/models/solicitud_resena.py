from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from app.db.database import Base


class EstadoSolicitud:
    PENDIENTE_USO = "Pendiente_Uso"
    UTILIZADA = "Utilizada"
    EXPIRADA = "Expirada"


class OrigenSolicitud:
    """Canal por el que se envía el enlace de reseña. Lo define qué datos de
    contacto cargó quien generó el enlace, no quién lo generó."""

    WHATSAPP = "WhatsApp"
    EMAIL = "Email"
    AMBOS = "Ambos"

    @classmethod
    def desde_contacto(cls, telefono: str | None, email: str | None) -> str:
        if telefono and email:
            return cls.AMBOS
        return cls.WHATSAPP if telefono else cls.EMAIL


class SolicitudResena(Base):
    __tablename__ = "solicitudes_resena"

    id_solicitud = Column(Integer, primary_key=True, index=True)
    oferente_id = Column(Integer, ForeignKey("oferentes.id_oferente", ondelete="CASCADE"), nullable=False, index=True)
    codigo_unico = Column(String(100), nullable=False, unique=True, index=True)

    # El nombre siempre se carga en el modal "Datos del Cliente"; de los dos
    # datos de contacto hay que cargar al menos uno (lo valida el schema).
    nombre_cliente = Column(String(100), nullable=False)
    telefono_cliente = Column(String(20), nullable=True)
    email_cliente = Column(String(255), nullable=True)

    origen = Column(String(50), nullable=False)
    estado = Column(String(50), nullable=False, default=EstadoSolicitud.PENDIENTE_USO)
    intentos_rechazo = Column(Integer, nullable=False, default=0)
    fecha_generacion = Column(DateTime(timezone=True), server_default=func.now())
    fecha_expiracion = Column(DateTime(timezone=True), nullable=False)

    oferente = relationship("Oferente", back_populates="solicitudes_resena")
    resenas = relationship("Resena", back_populates="solicitud", cascade="all, delete-orphan")

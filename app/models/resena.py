from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from app.db.database import Base


class EstadoResena:
    # Solo las reseñas originadas por WhatsApp arrancan sin verificar: el cliente
    # cargó su mail en la propia vista y todavía no confirmó que sea suyo. Una
    # reseña en este estado es invisible en todas las vistas y no suma al promedio.
    PENDIENTE_VERIFICACION = "Pendiente_Verificacion"
    PENDIENTE_APROBACION = "Pendiente_Aprobacion"
    APROBADA = "Aprobada"
    RECHAZADA = "Rechazada"


class Resena(Base):
    __tablename__ = "resenas"

    id_resena = Column(Integer, primary_key=True, index=True)
    oferente_id = Column(Integer, ForeignKey("oferentes.id_oferente", ondelete="CASCADE"), nullable=False, index=True)
    solicitud_id = Column(Integer, ForeignKey("solicitudes_resena.id_solicitud", ondelete="CASCADE"), nullable=False)

    nombre_cliente = Column(String(100), nullable=False)
    contacto_cliente_ingresado = Column(String(100), nullable=False)
    calificaciones_comentarios = Column(JSON, nullable=False)
    estado = Column(String(50), nullable=False, default=EstadoResena.PENDIENTE_APROBACION)
    fecha_creacion = Column(DateTime(timezone=True), server_default=func.now())

    oferente = relationship("Oferente", back_populates="resenas")
    solicitud = relationship("SolicitudResena", back_populates="resenas")

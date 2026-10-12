from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, func

from app.db.database import Base


class EmisionResena(Base):
    """Cada vez que sale un enlace de reseña hacia el cliente: el enlace nuevo y
    también cada reenvío del mismo. Los límites anti-spam (HU-01, 24 h) se cuentan
    sobre esta tabla y no sobre las solicitudes: reenviar un enlace existente no
    crea una solicitud nueva, y si no gastara cupo, el endpoint sería un spammer."""

    __tablename__ = "emisiones_resena"

    id_emision = Column(Integer, primary_key=True, index=True)
    solicitud_id = Column(Integer, ForeignKey("solicitudes_resena.id_solicitud", ondelete="CASCADE"), nullable=False, index=True)
    oferente_id = Column(Integer, ForeignKey("oferentes.id_oferente", ondelete="CASCADE"), nullable=False)
    # NULL cuando el enlace se generó solo con teléfono: no sale ningún correo,
    # pero igual cuenta para el límite por Profesional.
    email_cliente = Column(String(255), nullable=True)
    fecha_emision = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


Index("idx_emision_email_fecha", EmisionResena.email_cliente, EmisionResena.fecha_emision)
Index("idx_emision_oferente_fecha", EmisionResena.oferente_id, EmisionResena.fecha_emision)

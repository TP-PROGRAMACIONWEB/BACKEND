from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.db.database import Base


class TipoNotificacion:
    RESENA_NUEVA = "Resena_Nueva"
    MATRICULA_VALIDADA = "Matricula_Validada"
    MATRICULA_NO_ENCONTRADA = "Matricula_No_Encontrada"
    MATRICULA_TIMEOUT = "Matricula_Timeout"
    MATRICULA_YA_FIDELIZADA = "Matricula_Ya_Fidelizada"
    MATRICULA_REEMPLAZO_SOLICITADO = "Matricula_Reemplazo_Solicitado"


class EstadoNotificacion:
    PENDIENTE = "Pendiente"
    ACEPTADA = "Aceptada"
    RECHAZADA = "Rechazada"
    LEIDA = "Leida"


class Notificacion(Base):
    """Bandeja in-app (la campana). Reemplaza el aviso por correo al Profesional.

    Ver `docs/der-notificaciones.md` para el SQL propuesto y el ciclo de vida.
    """

    __tablename__ = "notificaciones"

    id_notificacion = Column(Integer, primary_key=True, index=True)

    # Apunta a USUARIO y no a OFERENTE a propósito: el Administrador también
    # recibe notificaciones (autorización de reemplazo de matrícula).
    usuario_id = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="CASCADE"), nullable=False, index=True)

    tipo = Column(String(50), nullable=False)
    mensaje = Column(Text, nullable=False)

    # True -> espera una decisión (Aceptar / Rechazar) y suma al contador de la
    # campana. False -> informativa, se cierra pasando a Leida.
    requiere_accion = Column(Boolean, nullable=False, default=False)
    estado = Column(String(50), nullable=False, default=EstadoNotificacion.PENDIENTE)

    resena_id = Column(Integer, ForeignKey("resenas.id_resena", ondelete="CASCADE"), nullable=True)

    # Momento del hecho notificado: para HU-01, cuándo cargó la reseña el
    # cliente, no cuándo la moderó el Profesional.
    fecha_creacion = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    fecha_resolucion = Column(DateTime(timezone=True), nullable=True)

    usuario = relationship("Usuario", back_populates="notificaciones")
    resena = relationship("Resena", back_populates="notificaciones")


Index("idx_notificacion_usuario_estado", Notificacion.usuario_id, Notificacion.estado)
Index("idx_notificacion_fecha", Notificacion.fecha_creacion.desc())

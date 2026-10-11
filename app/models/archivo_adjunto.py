from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, SmallInteger, String, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.db.database import Base


class TipoArchivo:
    PERFIL = "Perfil"
    PORTADA = "Portada"
    TRABAJO = "Trabajo"


class ArchivoAdjunto(Base):
    """Imagen subida a Supabase Storage (HU-04 T06). Reutiliza la tabla del DER
    para foto de perfil, portada y fotos de trabajos.

    `storage_path` es la clave del objeto en el bucket; la URL pública se arma
    a partir de ella. Nunca se guarda una URL completa.
    """

    __tablename__ = "archivos_adjuntos"
    __table_args__ = (
        # Dos fotos del mismo trabajo no pueden compartir posición. NULL en
        # perfil y portada: los NULL no chocan entre sí en la unique.
        UniqueConstraint("trabajo_id", "orden", name="uq_archivo_trabajo_orden"),
        CheckConstraint("orden IS NULL OR orden BETWEEN 1 AND 5", name="ck_archivo_orden_rango"),
    )

    id_archivo = Column(Integer, primary_key=True, index=True)
    oferente_id = Column(Integer, ForeignKey("oferentes.id_oferente", ondelete="CASCADE"), nullable=False, index=True)
    tipo = Column(String(50), nullable=False)
    storage_path = Column(String(255), nullable=False, unique=True)
    content_type = Column(String(50), nullable=False)
    tamano_bytes = Column(Integer, nullable=False)
    trabajo_id = Column(Integer, ForeignKey("trabajos_realizados.id_trabajo", ondelete="CASCADE"), nullable=True, index=True)
    orden = Column(SmallInteger, nullable=True)
    fecha_subida = Column(DateTime(timezone=True), server_default=func.now())

    oferente = relationship("Oferente", back_populates="archivos")
    trabajo = relationship("TrabajoRealizado", back_populates="fotos")

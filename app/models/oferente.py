from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Time,
)
from sqlalchemy.orm import relationship

from app.db.database import Base


class EstadoVerificacion:
    PENDIENTE = "Pendiente"
    VERIFICADO = "Verificado"
    RECHAZADO = "Rechazado"


class Oferente(Base):
    __tablename__ = "oferentes"

    # PK compartida: id_oferente NO autoincrementa, es también FK 1-a-1 hacia
    # usuarios.id_usuario. SQLAlchemy desactiva el autoincrement automáticamente
    # en una columna Integer que es a la vez PK y FK.
    id_oferente = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="CASCADE"), primary_key=True)
    categoria_id = Column(Integer, ForeignKey("categorias.id_categoria"), nullable=True)

    nombre = Column(String(100), nullable=False)
    apellido = Column(String(100), nullable=False)
    dni_cuit = Column(String(50), nullable=False, unique=True)
    telefono = Column(String(50), nullable=False)
    numero_matricula = Column(String(100), nullable=True)
    estado_verificacion = Column(String(50), nullable=False, default=EstadoVerificacion.PENDIENTE)

    latitud = Column(Numeric(10, 8), nullable=True)
    longitud = Column(Numeric(11, 8), nullable=True)
    radio_cobertura_km = Column(Numeric(5, 2), nullable=True)

    hora_inicio_atencion = Column(Time, nullable=True)
    hora_fin_atencion = Column(Time, nullable=True)
    disponible_emergencia = Column(Boolean, nullable=False, default=False)

    promedio_calificacion = Column(Numeric(3, 2), nullable=False, default=0)
    descripcion = Column(Text, nullable=True)
    cantidad_rechazos_acumulados = Column(Integer, nullable=False, default=0)

    usuario = relationship("Usuario", back_populates="oferente")
    categoria = relationship("Categoria", back_populates="oferentes")
    archivos = relationship("ArchivoAdjunto", back_populates="oferente", cascade="all, delete-orphan")
    solicitudes_resena = relationship("SolicitudResena", back_populates="oferente", cascade="all, delete-orphan")
    resenas = relationship("Resena", back_populates="oferente", cascade="all, delete-orphan")
    alertas = relationship("AlertaAdministrador", back_populates="oferente", cascade="all, delete-orphan")

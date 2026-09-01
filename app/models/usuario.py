import enum

from sqlalchemy import Column, DateTime, Enum, Integer, String, func
from sqlalchemy.orm import relationship

from app.db.database import Base


class RolUsuario(str, enum.Enum):
    OFERENTE = "oferente"
    ADMINISTRADOR = "administrador"


class EstadoCuenta(str, enum.Enum):
    ACTIVA = "activa"
    SUSPENDIDA = "suspendida"
    BLOQUEADA = "bloqueada"


class Usuario(Base):
    __tablename__ = "usuarios"

    id_usuario = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    rol = Column(Enum(RolUsuario), nullable=False, default=RolUsuario.OFERENTE)
    estado_cuenta = Column(Enum(EstadoCuenta), nullable=False, default=EstadoCuenta.ACTIVA)
    fecha_registro = Column(DateTime(timezone=True), server_default=func.now())

    oferente = relationship("Oferente", back_populates="usuario", uselist=False)

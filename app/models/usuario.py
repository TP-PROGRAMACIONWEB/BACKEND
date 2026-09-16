import enum

from sqlalchemy import Column, DateTime, Enum, Integer, String, func
from sqlalchemy.orm import relationship

from app.db.database import Base


class RolUsuario(str, enum.Enum):
    OFERENTE = "Oferente"
    ADMINISTRADOR = "Administrador"


class EstadoCuenta:
    ACTIVA = "Activa"
    SUSPENDIDA = "Suspendida"
    BLOQUEADA = "Bloqueada"


class Usuario(Base):
    __tablename__ = "usuarios"

    id_usuario = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    # Nombre que muestra el perfil (HU-03/CA02). NULL para las cuentas que
    # todavía no iniciaron sesión con Google: el login por email/password no
    # lo pide. Se actualiza en cada login con Google, que es la fuente de
    # verdad de este dato para esas cuentas.
    nombre = Column(String(150), nullable=True)
    rol = Column(
        Enum(
            RolUsuario,
            name="rol_usuario",
            native_enum=False,
            length=50,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=RolUsuario.OFERENTE,
    )
    estado_cuenta = Column(String(50), nullable=False, default=EstadoCuenta.ACTIVA)
    fecha_registro = Column(DateTime(timezone=True), server_default=func.now())

    oferente = relationship("Oferente", back_populates="usuario", uselist=False)
    notificaciones = relationship("Notificacion", back_populates="usuario", cascade="all, delete-orphan")

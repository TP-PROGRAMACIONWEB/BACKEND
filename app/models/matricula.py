from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.db.database import Base


class TipoProfesionalMatricula:
    GASISTA = "Gasista"
    AIRE_ACONDICIONADO = "Aire acondicionado"


class ResultadoValidacion:
    VALIDADA = "Validada"
    NO_ENCONTRADA = "No_Encontrada"
    TIMEOUT = "Timeout"
    YA_FIDELIZADA = "Ya_Fidelizada"
    REEMPLAZO_SOLICITADO = "Reemplazo_Solicitado"
    VENCIDA = "Vencida"
    NOMBRE_NO_COINCIDE = "Nombre_No_Coincide"


class EstadoReemplazo:
    PENDIENTE = "Pendiente"
    AUTORIZADO = "Autorizado"
    DENEGADO = "Denegado"
    SUPERSEDED = "Superseded"


class PadronMatricula(Base):
    """El padrón de matriculados, cargado a la base desde los `.md` de
    `app/db/padrones/` por el seed. La consulta de HU-02 se hace contra esta
    tabla, no leyendo el archivo en cada request."""

    __tablename__ = "padron_matriculas"
    __table_args__ = (UniqueConstraint("tipo_profesional", "numero_matricula", name="uq_padron_tipo_numero"),)

    id_padron = Column(Integer, primary_key=True, index=True)
    tipo_profesional = Column(String(50), nullable=False, index=True)
    numero_matricula = Column(String(20), nullable=False, index=True)
    nombre_matriculado = Column(String(200), nullable=False)
    categoria = Column(String(50), nullable=False)
    fecha_vencimiento = Column(Date, nullable=False)


class Matricula(Base):
    """Matrícula fidelizada por un Oferente. Una por oficio: mientras haya un
    reemplazo pendiente de autorización, esta fila no se toca, así que el
    Oferente conserva el distintivo de verificado con la matrícula vieja."""

    __tablename__ = "matriculas"
    __table_args__ = (UniqueConstraint("oferente_id", "tipo_profesional", name="uq_matricula_oferente_tipo"),)

    id_matricula = Column(Integer, primary_key=True, index=True)
    oferente_id = Column(Integer, ForeignKey("oferentes.id_oferente", ondelete="CASCADE"), nullable=False, index=True)
    tipo_profesional = Column(String(50), nullable=False)
    numero_matricula = Column(String(20), nullable=False)
    categoria = Column(String(50), nullable=False)
    fecha_vencimiento = Column(Date, nullable=False)
    fecha_fidelizacion = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    oferente = relationship("Oferente", back_populates="matriculas")


class ValidacionMatricula(Base):
    """Historial de **todos** los intentos de validación, incluidos los
    fallidos. `categoria_padron`/`fecha_vencimiento_padron` son el snapshot
    del padrón en el momento del intento: evitan volver a consultarlo al
    resolver un reemplazo. `estado_reemplazo` solo se usa cuando
    `resultado = Reemplazo_Solicitado`; es la fuente de verdad de si ese
    pedido sigue esperando al Administrador."""

    __tablename__ = "validaciones_matricula"

    id_validacion = Column(Integer, primary_key=True, index=True)
    oferente_id = Column(Integer, ForeignKey("oferentes.id_oferente", ondelete="CASCADE"), nullable=False, index=True)
    tipo_profesional = Column(String(50), nullable=False)
    numero_matricula = Column(String(20), nullable=False)
    resultado = Column(String(50), nullable=False)

    categoria_padron = Column(String(50), nullable=True)
    fecha_vencimiento_padron = Column(Date, nullable=True)

    estado_reemplazo = Column(String(50), nullable=True)

    fecha_intento = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    oferente = relationship("Oferente", back_populates="validaciones_matricula")

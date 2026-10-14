from sqlalchemy import Boolean, Column, ForeignKey, Integer, Numeric, String, Text, Time
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
    #
    # La existencia de la fila es el flag de "registro completo" (HU-04): un
    # Usuario con rol Oferente y sin esta fila todavía no confirmo el formulario.
    id_oferente = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="CASCADE"), primary_key=True)
    categoria_id = Column(Integer, ForeignKey("categorias.id_categoria"), nullable=True)

    # Nombre y apellido en un solo campo (o razón social). Es lo que se compara con el padrón (HU-02).
    nombre = Column(String(150), nullable=False)
    dni_cuit = Column(String(50), nullable=False, unique=True)
    telefono = Column(String(50), nullable=False)
    # Legado de Sprint 1: el número de matrícula vive ahora en MATRICULAS (HU-02).
    # Sale de los schemas; dropear la columna se coordina con el compañero.
    numero_matricula = Column(String(100), nullable=True)
    estado_verificacion = Column(String(50), nullable=False, default=EstadoVerificacion.PENDIENTE)

    especialidad = Column(String(100), nullable=True)
    # Código del catálogo de experiencia (MENOS_1, 1_A_2, ...). Ver app/core/catalogos.py.
    experiencia = Column(String(20), nullable=True)

    latitud = Column(Numeric(10, 8), nullable=True)
    longitud = Column(Numeric(11, 8), nullable=True)
    radio_cobertura_km = Column(Numeric(5, 2), nullable=True)

    # Obligatorios para los registros nuevos (los impone el schema). Quedan
    # nullable en la base porque las filas anteriores a Sprint 2 pueden no tenerlos.
    hora_inicio_atencion = Column(Time, nullable=True)
    hora_fin_atencion = Column(Time, nullable=True)
    disponible_emergencia = Column(Boolean, nullable=False, default=False)
    info_guardia = Column(String(200), nullable=True)

    promedio_calificacion = Column(Numeric(3, 2), nullable=False, default=0)
    descripcion = Column(Text, nullable=True)
    cantidad_rechazos_acumulados = Column(Integer, nullable=False, default=0)

    usuario = relationship("Usuario", back_populates="oferente")
    categoria = relationship("Categoria", back_populates="oferentes")
    dias_atencion = relationship(
        "OferenteDiaAtencion",
        back_populates="oferente",
        cascade="all, delete-orphan",
        order_by="OferenteDiaAtencion.dia",
    )
    archivos = relationship("ArchivoAdjunto", back_populates="oferente", cascade="all, delete-orphan")
    trabajos = relationship(
        "TrabajoRealizado",
        back_populates="oferente",
        cascade="all, delete-orphan",
        order_by="TrabajoRealizado.fecha_creacion.desc()",
    )
    solicitudes_resena = relationship("SolicitudResena", back_populates="oferente", cascade="all, delete-orphan")
    resenas = relationship("Resena", back_populates="oferente", cascade="all, delete-orphan")
    alertas = relationship("AlertaAdministrador", back_populates="oferente", cascade="all, delete-orphan")
    matriculas = relationship("Matricula", back_populates="oferente", cascade="all, delete-orphan")
    validaciones_matricula = relationship("ValidacionMatricula", back_populates="oferente", cascade="all, delete-orphan")

    @property
    def tiene_matricula_validada(self) -> bool:
        """Distintivo de verificado de HU-02: aparece con al menos una
        matrícula fidelizada, sin importar el `estado_verificacion` manual
        (que queda como override aparte del Administrador)."""
        return bool(self.matriculas)

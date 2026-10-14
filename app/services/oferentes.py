"""Alta, edición y armado de los perfiles de Oferente (HU-04).

Las salidas se arman acá y no en el router: el perfil público y el privado
comparten casi todo, y la regla de "qué ve cada uno" (D7) tiene que estar en un
único lugar.
"""

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.catalogos import ETIQUETA_EXPERIENCIA
from app.core.errores import error_negocio, error_validacion
from app.models.archivo_adjunto import ArchivoAdjunto, TipoArchivo
from app.models.categoria import Categoria, EstadoCategoria
from app.models.oferente import EstadoVerificacion, Oferente
from app.models.oferente_dia_atencion import OferenteDiaAtencion
from app.models.resena import EstadoResena, Resena
from app.models.trabajo_realizado import TrabajoRealizado
from app.models.usuario import RolUsuario, Usuario
from app.schemas.oferente import (
    CategoriaRef,
    ExperienciaRef,
    MatriculaRef,
    OferenteEdicion,
    OferentePrivadoOut,
    OferentePublicoOut,
    OferenteRegistro,
)
from app.services.storage import url_publica

# Campos que la edición no puede dejar en NULL: el registro los exige.
CAMPOS_NO_NULOS = {
    "nombre",
    "telefono",
    "categoria_id",
    "dias_atencion",
    "hora_inicio_atencion",
    "hora_fin_atencion",
    "disponible_emergencia",
}


def _hora(valor) -> str | None:
    return valor.strftime("%H:%M") if valor is not None else None


def _url_unica(db: Session, oferente_id: int, tipo: str) -> str | None:
    """Foto de perfil o portada: hay una sola vigente por tipo."""
    archivo = (
        db.query(ArchivoAdjunto)
        .filter(ArchivoAdjunto.oferente_id == oferente_id, ArchivoAdjunto.tipo == tipo, ArchivoAdjunto.trabajo_id.is_(None))
        .first()
    )
    return url_publica(archivo.storage_path) if archivo else None


def armar_publica(db: Session, oferente: Oferente) -> OferentePublicoOut:
    cantidad_resenas = (
        db.query(func.count(Resena.id_resena))
        .filter(Resena.oferente_id == oferente.id_oferente, Resena.estado == EstadoResena.ACEPTADA)
        .scalar()
    )
    cantidad_trabajos = (
        db.query(func.count(TrabajoRealizado.id_trabajo)).filter(TrabajoRealizado.oferente_id == oferente.id_oferente).scalar()
    )
    categoria = oferente.categoria
    return OferentePublicoOut(
        id_oferente=oferente.id_oferente,
        nombre=oferente.nombre,
        categoria_id=oferente.categoria_id,
        categoria=CategoriaRef(id_categoria=categoria.id_categoria, nombre=categoria.nombre) if categoria else None,
        especialidad=oferente.especialidad,
        experiencia=(
            ExperienciaRef(codigo=oferente.experiencia, etiqueta=ETIQUETA_EXPERIENCIA[oferente.experiencia])
            if oferente.experiencia
            else None
        ),
        telefono=oferente.telefono,
        email=oferente.usuario.email,
        dias_atencion=[dia.dia for dia in oferente.dias_atencion],
        hora_inicio_atencion=_hora(oferente.hora_inicio_atencion),
        hora_fin_atencion=_hora(oferente.hora_fin_atencion),
        disponible_emergencia=oferente.disponible_emergencia,
        info_guardia=oferente.info_guardia,
        descripcion=oferente.descripcion,
        latitud=oferente.latitud,
        longitud=oferente.longitud,
        radio_cobertura_km=oferente.radio_cobertura_km,
        promedio_calificacion=oferente.promedio_calificacion,
        cantidad_resenas=cantidad_resenas,
        cantidad_trabajos=cantidad_trabajos,
        tiene_matricula_validada=oferente.tiene_matricula_validada,
        matriculas=[MatriculaRef(tipo_profesional=m.tipo_profesional, numero_matricula=m.numero_matricula) for m in oferente.matriculas],
        foto_perfil_url=_url_unica(db, oferente.id_oferente, TipoArchivo.PERFIL),
        portada_url=_url_unica(db, oferente.id_oferente, TipoArchivo.PORTADA),
    )


def armar_privada(db: Session, oferente: Oferente) -> OferentePrivadoOut:
    publica = armar_publica(db, oferente)
    return OferentePrivadoOut(
        **publica.model_dump(),
        dni_cuit=oferente.dni_cuit,
        estado_verificacion=oferente.estado_verificacion,
        cantidad_rechazos_acumulados=oferente.cantidad_rechazos_acumulados,
    )


def validar_categoria(db: Session, categoria_id: int) -> None:
    categoria = db.get(Categoria, categoria_id)
    if categoria is None or categoria.estado != EstadoCategoria.ACTIVA:
        raise error_validacion("categoria_id", "categoria_invalida", "Seleccioná una categoría de la lista")


def reemplazar_dias(db: Session, oferente_id: int, dias: list[int]) -> None:
    # Borrado por query y no por la colección: la PK (oferente, día) se repite
    # entre lo viejo y lo nuevo, y el orden de los INSERT/DELETE no se controla.
    db.query(OferenteDiaAtencion).filter(OferenteDiaAtencion.oferente_id == oferente_id).delete(synchronize_session=False)
    for dia in dias:
        db.add(OferenteDiaAtencion(oferente_id=oferente_id, dia=dia))


def crear_oferente(db: Session, usuario: Usuario, datos: OferenteRegistro) -> Oferente:
    """CA03: crea el perfil y sus días en una sola transacción. El doble clic
    (caso A26) llega como dos INSERT con la misma PK: el segundo falla con
    IntegrityError y se responde 409 perfil_existente."""
    if usuario.rol != RolUsuario.OFERENTE:
        raise error_negocio(403, "rol_invalido", "Solo los usuarios con rol Oferente pueden registrarse como Profesional")
    if db.get(Oferente, usuario.id_usuario) is not None:
        raise error_negocio(409, "perfil_existente", "Ya completaste el registro de Profesional")

    validar_categoria(db, datos.categoria_id)
    if db.query(Oferente.id_oferente).filter(Oferente.dni_cuit == datos.dni_cuit).first():
        raise error_negocio(409, "dni_cuit_duplicado", "Ese DNI/CUIT ya está registrado")

    oferente = Oferente(
        id_oferente=usuario.id_usuario,
        nombre=datos.nombre,
        dni_cuit=datos.dni_cuit,
        telefono=datos.telefono,
        categoria_id=datos.categoria_id,
        especialidad=datos.especialidad,
        experiencia=datos.experiencia,
        hora_inicio_atencion=datos.hora_inicio_atencion,
        hora_fin_atencion=datos.hora_fin_atencion,
        disponible_emergencia=datos.disponible_emergencia,
        info_guardia=datos.info_guardia,
        estado_verificacion=EstadoVerificacion.PENDIENTE,
    )
    try:
        db.add(oferente)
        db.flush()
        reemplazar_dias(db, oferente.id_oferente, datos.dias_atencion)
        db.commit()
    except IntegrityError:
        db.rollback()
        if db.get(Oferente, usuario.id_usuario) is not None:
            raise error_negocio(409, "perfil_existente", "Ya completaste el registro de Profesional")
        raise error_negocio(409, "dni_cuit_duplicado", "Ese DNI/CUIT ya está registrado")

    db.refresh(oferente)
    return oferente


def aplicar_edicion(db: Session, oferente: Oferente, datos: OferenteEdicion) -> Oferente:
    cambios = datos.model_dump(exclude_unset=True)

    for campo in CAMPOS_NO_NULOS:
        if campo in cambios and cambios[campo] is None:
            raise error_validacion(campo, "requerido", "Complete este campo")

    if "nombre" in cambios:
        cambio_identidad = cambios["nombre"] != oferente.nombre
        # Si ya hay una matrícula fidelizada, la identidad queda atada al
        # distintivo de verificado: cambiarla dejaría el distintivo colgado de
        # otra persona (HU-04, D18).
        if cambio_identidad and oferente.matriculas:
            raise error_negocio(
                409,
                "nombre_bloqueado_por_matricula",
                "No podés cambiar el nombre mientras tengas una matrícula fidelizada",
            )

    if "categoria_id" in cambios:
        validar_categoria(db, cambios["categoria_id"])

    inicio = cambios.get("hora_inicio_atencion", oferente.hora_inicio_atencion)
    fin = cambios.get("hora_fin_atencion", oferente.hora_fin_atencion)
    if inicio is not None and fin is not None and fin <= inicio:
        raise error_validacion("hora_fin_atencion", "horario_invalido", "El horario de cierre tiene que ser posterior a la apertura")

    dias = cambios.pop("dias_atencion", None)
    for campo, valor in cambios.items():
        setattr(oferente, campo, valor)
    if dias is not None:
        reemplazar_dias(db, oferente.id_oferente, dias)
    if not oferente.disponible_emergencia:
        oferente.info_guardia = None

    db.commit()
    db.refresh(oferente)
    return oferente

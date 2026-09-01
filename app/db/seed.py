"""Carga datos de prueba para poder demostrar el flujo de Sprint 1: categorías
de oficios, Oferentes de ejemplo (con su Usuario asociado) y una solicitud de
reseña ya generada. Idempotente: se puede correr varias veces sin duplicar datos.

Uso: python -m app.db.seed
"""

from app.core.security import hash_password
from app.db.database import Base, SessionLocal, engine
from app.models import alerta_admin, archivo_adjunto, resena  # noqa: F401 — registran sus mappers
from app.models.categoria import Categoria
from app.models.oferente import EstadoVerificacion, Oferente
from app.models.solicitud_resena import SolicitudResena
from app.models.usuario import RolUsuario, Usuario

PASSWORD_SEED = "Offix2026!"

CATEGORIAS = [
    ("Electricista", "Instalaciones y reparaciones eléctricas domiciliarias e industriales."),
    ("Gasista", "Instalación y mantenimiento de gas natural y envasado."),
    ("Plomero", "Instalación y reparación de cañerías, sanitarios y desagües."),
    ("Técnico en Aire Acondicionado", "Instalación y service de equipos de climatización."),
    ("Albañil", "Construcción, reformas y reparaciones edilicias."),
    ("Carpintero", "Fabricación y reparación de muebles y estructuras de madera."),
]

OFERENTES_DEMO = [
    dict(
        email="juan.perez@offix.test",
        nombre="Juan",
        apellido="Pérez",
        categoria="Electricista",
        dni_cuit="20-30111222-3",
        telefono="+54 3564 400111",
        estado_verificacion=EstadoVerificacion.VERIFICADO,
    ),
    dict(
        email="maria.gomez@offix.test",
        nombre="María",
        apellido="Gómez",
        categoria="Gasista",
        dni_cuit="27-28333444-5",
        telefono="+54 3564 400222",
        estado_verificacion=EstadoVerificacion.VERIFICADO,
    ),
    dict(
        email="carlos.fernandez@offix.test",
        nombre="Carlos",
        apellido="Fernández",
        categoria="Plomero",
        dni_cuit="20-25555666-7",
        telefono="+54 3564 400333",
        estado_verificacion=EstadoVerificacion.PENDIENTE,
    ),
    dict(
        email="lucia.rodriguez@offix.test",
        nombre="Lucía",
        apellido="Rodríguez",
        categoria="Técnico en Aire Acondicionado",
        dni_cuit="27-26777888-9",
        telefono="+54 3564 400444",
        estado_verificacion=EstadoVerificacion.VERIFICADO,
    ),
    dict(
        email="sergio.diaz@offix.test",
        nombre="Sergio",
        apellido="Díaz",
        categoria="Albañil",
        dni_cuit="20-31999000-1",
        telefono="+54 3564 400555",
        estado_verificacion=EstadoVerificacion.PENDIENTE,
    ),
    dict(
        email="ana.torres@offix.test",
        nombre="Ana",
        apellido="Torres",
        categoria="Carpintero",
        dni_cuit="27-29222333-4",
        telefono="+54 3564 400666",
        estado_verificacion=EstadoVerificacion.RECHAZADO,
    ),
]

CODIGO_SOLICITUD_DEMO = "DEMO-CODE-0001"


def get_or_create_categoria(db, nombre: str, descripcion: str) -> Categoria:
    categoria = db.query(Categoria).filter(Categoria.nombre == nombre).first()
    if categoria:
        return categoria
    categoria = Categoria(nombre=nombre, descripcion=descripcion)
    db.add(categoria)
    db.flush()
    return categoria


def get_or_create_oferente(db, categorias: dict[str, Categoria], datos: dict) -> Oferente:
    usuario = db.query(Usuario).filter(Usuario.email == datos["email"]).first()
    if usuario and usuario.oferente:
        return usuario.oferente

    if not usuario:
        usuario = Usuario(
            email=datos["email"],
            password_hash=hash_password(PASSWORD_SEED),
            rol=RolUsuario.OFERENTE,
        )
        db.add(usuario)
        db.flush()  # asigna id_usuario sin cerrar la transacción

    oferente = Oferente(
        id_oferente=usuario.id_usuario,
        categoria_id=categorias[datos["categoria"]].id_categoria,
        nombre=datos["nombre"],
        apellido=datos["apellido"],
        dni_cuit=datos["dni_cuit"],
        telefono=datos["telefono"],
        estado_verificacion=datos["estado_verificacion"],
        descripcion=f"{datos['nombre']} {datos['apellido']} — {datos['categoria']} de prueba para demo de Sprint 1.",
    )
    db.add(oferente)
    db.flush()
    return oferente


def get_or_create_admin(db) -> Usuario:
    admin = db.query(Usuario).filter(Usuario.email == "admin@offix.test").first()
    if admin:
        return admin
    admin = Usuario(
        email="admin@offix.test",
        password_hash=hash_password(PASSWORD_SEED),
        rol=RolUsuario.ADMINISTRADOR,
    )
    db.add(admin)
    db.flush()
    return admin


def get_or_create_solicitud_demo(db, oferente: Oferente) -> SolicitudResena:
    solicitud = db.query(SolicitudResena).filter(SolicitudResena.codigo_unico == CODIGO_SOLICITUD_DEMO).first()
    if solicitud:
        return solicitud
    solicitud = SolicitudResena(
        oferente_id=oferente.id_oferente,
        codigo_unico=CODIGO_SOLICITUD_DEMO,
        contacto_referencia_cliente="Cliente Demo - 341-5551234",
    )
    db.add(solicitud)
    db.flush()
    return solicitud


def run():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        categorias = {nombre: get_or_create_categoria(db, nombre, descripcion) for nombre, descripcion in CATEGORIAS}

        oferentes = [get_or_create_oferente(db, categorias, datos) for datos in OFERENTES_DEMO]

        get_or_create_admin(db)
        get_or_create_solicitud_demo(db, oferentes[0])

        db.commit()
        print(f"Datos de prueba cargados/verificados correctamente ({len(categorias)} categorías, {len(oferentes)} oferentes).")
        print(f"Usuario admin: admin@offix.test / password: {PASSWORD_SEED}")
        print(f"Oferentes de ejemplo: password para todos: {PASSWORD_SEED}")
        print(f"Código de solicitud de reseña de demo (sin login): {CODIGO_SOLICITUD_DEMO}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()

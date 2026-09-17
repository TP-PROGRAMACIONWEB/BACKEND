"""Carga datos de prueba para poder demostrar el flujo de Sprint 1: categorías
de oficios, Oferentes de ejemplo (con su Usuario asociado), solicitudes de reseña
ya generadas —una por canal— y una notificación pendiente en la bandeja, para
poder mostrar la campana con contador sin generar una reseña primero. También
carga los padrones de matriculados de HU-02 (Gasista completo; Aire
acondicionado parcial — ver PADRONES más abajo).
Idempotente: se puede correr varias veces sin duplicar datos.

Uso: python -m app.db.seed
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.core.config import settings
from app.core.security import hash_password
from app.db.database import SessionLocal, preparar_esquema
from app.models import alerta_admin, archivo_adjunto  # noqa: F401 — registran sus mappers
from app.models.categoria import Categoria
from app.models.matricula import PadronMatricula, TipoProfesionalMatricula
from app.models.notificacion import Notificacion
from app.models.oferente import EstadoVerificacion, Oferente
from app.models.resena import EstadoResena, Resena
from app.models.solicitud_resena import EstadoSolicitud, OrigenSolicitud, SolicitudResena
from app.models.usuario import RolUsuario, Usuario
from app.services.notificaciones import crear_notificacion_resena_nueva
from app.services.padrones import parsear_padron_json, parsear_padron_md

PADRONES_DIR = Path(__file__).parent / "padrones"

# (tipo, archivo, parser). Gasistas: 68 matriculados, padrón completo.
# Aire acondicionado: 49 matriculados válidos (50 filas del export menos una
# de prueba), y es **parcial** — el export trae 50 de 77 totales, falta la
# página 2. Ver docs/plan-sprint-1.md, pregunta abierta #1.
PADRONES = [
    (TipoProfesionalMatricula.GASISTA, PADRONES_DIR / "gasistas.md", parsear_padron_md),
    (TipoProfesionalMatricula.AIRE_ACONDICIONADO, PADRONES_DIR / "aire-acondicionado.json", parsear_padron_json),
]
MATRICULA_DEMO_GASISTA = "1000008919"  # ALESSI MARIA CLARA, la primera fila del padrón real.
MATRICULA_DEMO_AIRE_ACONDICIONADO = "28408435"  # ABATEDAGA MARTIN, la primera fila del export.

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
        email="juan.perez@offix.example.com",
        nombre="Juan",
        apellido="Pérez",
        categoria="Electricista",
        dni_cuit="20-30111222-3",
        telefono="+54 3564 400111",
        estado_verificacion=EstadoVerificacion.VERIFICADO,
    ),
    dict(
        email="maria.gomez@offix.example.com",
        # Nombre real del padrón de Gasistas (matrícula 1000008919), para
        # poder demostrar HU-02 de punta a punta: con un nombre inventado el
        # match contra el padrón lo rechaza.
        nombre="María Clara",
        apellido="Alessi",
        categoria="Gasista",
        dni_cuit="27-28333444-5",
        telefono="+54 3564 400222",
        estado_verificacion=EstadoVerificacion.VERIFICADO,
    ),
    dict(
        email="carlos.fernandez@offix.example.com",
        nombre="Carlos",
        apellido="Fernández",
        categoria="Plomero",
        dni_cuit="20-25555666-7",
        telefono="+54 3564 400333",
        estado_verificacion=EstadoVerificacion.PENDIENTE,
    ),
    dict(
        email="lucia.rodriguez@offix.example.com",
        # Nombre real del padrón de Aire acondicionado (matrícula 28408435),
        # igual que se hizo con la Gasista de demo: con un nombre inventado el
        # match contra el padrón la rechaza.
        nombre="Martin",
        apellido="Abatedaga",
        categoria="Técnico en Aire Acondicionado",
        dni_cuit="27-26777888-9",
        telefono="+54 3564 400444",
        estado_verificacion=EstadoVerificacion.VERIFICADO,
    ),
    dict(
        email="sergio.diaz@offix.example.com",
        nombre="Sergio",
        apellido="Díaz",
        categoria="Albañil",
        dni_cuit="20-31999000-1",
        telefono="+54 3564 400555",
        estado_verificacion=EstadoVerificacion.PENDIENTE,
    ),
    dict(
        email="ana.torres@offix.example.com",
        nombre="Ana",
        apellido="Torres",
        categoria="Carpintero",
        dni_cuit="27-29222333-4",
        telefono="+54 3564 400666",
        estado_verificacion=EstadoVerificacion.RECHAZADO,
    ),
]

CODIGO_SOLICITUD_EMAIL = "DEMO-EMAIL-0001"
CODIGO_SOLICITUD_WHATSAPP = "DEMO-WPP-0001"
CODIGO_SOLICITUD_ACEPTADA = "DEMO-ACEPTADA-0001"


def fecha_expiracion() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=settings.solicitud_resena_dias_validez)


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
        # nombre/apellido sí se sincronizan en cada corrida: son los que
        # habilitan el match contra el padrón (HU-02), y quedaron mal una vez
        # en la nube porque acá no se actualizaban en un Oferente ya creado.
        oferente = usuario.oferente
        oferente.nombre = datos["nombre"]
        oferente.apellido = datos["apellido"]
        return oferente

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


def get_or_create_padron(db) -> int:
    """Carga los padrones de matriculados a la base si todavía no están.
    Devuelve la cantidad de filas cargadas (0 si ya estaban)."""
    cargadas = 0
    for tipo, path, parser in PADRONES:
        if db.query(PadronMatricula).filter(PadronMatricula.tipo_profesional == tipo).first():
            continue
        for fila in parser(path):
            db.add(
                PadronMatricula(
                    tipo_profesional=tipo,
                    numero_matricula=fila.numero_matricula,
                    nombre_matriculado=fila.nombre_matriculado,
                    categoria=fila.categoria,
                    fecha_vencimiento=fila.fecha_vencimiento,
                )
            )
            cargadas += 1
    db.flush()
    return cargadas


def get_or_create_admin(db) -> Usuario:
    admin = db.query(Usuario).filter(Usuario.email == "admin@offix.example.com").first()
    if admin:
        return admin
    admin = Usuario(
        email="admin@offix.example.com",
        password_hash=hash_password(PASSWORD_SEED),
        rol=RolUsuario.ADMINISTRADOR,
    )
    db.add(admin)
    db.flush()
    return admin


def get_or_create_solicitud(db, oferente: Oferente, codigo: str, **datos_cliente) -> SolicitudResena:
    """El canal (`origen`) sale de qué datos de contacto se cargaron."""
    solicitud = db.query(SolicitudResena).filter(SolicitudResena.codigo_unico == codigo).first()
    if solicitud:
        return solicitud
    solicitud = SolicitudResena(
        oferente_id=oferente.id_oferente,
        codigo_unico=codigo,
        origen=OrigenSolicitud.desde_contacto(datos_cliente.get("telefono_cliente"), datos_cliente.get("email_cliente")),
        fecha_expiracion=fecha_expiracion(),
        **datos_cliente,
    )
    db.add(solicitud)
    db.flush()
    return solicitud


def get_or_create_resena_aceptada(db, oferente: Oferente) -> Resena:
    """Deja una reseña ya publicada para que el perfil muestre un promedio real en la demo."""
    solicitud = get_or_create_solicitud(
        db,
        oferente,
        CODIGO_SOLICITUD_ACEPTADA,
        nombre_cliente="Marta Ibáñez",
        email_cliente="marta.ibanez@offix.example.com",
    )
    resena = db.query(Resena).filter(Resena.solicitud_id == solicitud.id_solicitud).first()
    if resena:
        return resena

    criterios = {"precio": 4.0, "calidad": 5.0, "atencion": 4.5, "puntualidad": 4.5}
    resena = Resena(
        oferente_id=oferente.id_oferente,
        solicitud_id=solicitud.id_solicitud,
        nombre_cliente="Marta Ibáñez",
        contacto_cliente_ingresado="marta.ibanez@offix.example.com",
        calificaciones_comentarios={
            "puntuacion_global": round(sum(criterios.values()) / len(criterios), 2),
            "criterios": criterios,
            "comentario": "Muy prolijo y puntual. Lo recomiendo.",
        },
        estado=EstadoResena.ACEPTADA,
    )
    solicitud.estado = EstadoSolicitud.UTILIZADA
    oferente.promedio_calificacion = resena.calificaciones_comentarios["puntuacion_global"]
    db.add(resena)
    db.flush()
    return resena


def get_or_create_notificacion_pendiente(db, resena: Resena, solicitud: SolicitudResena) -> Notificacion:
    """Una notificación en la campana del Oferente, para poder mostrar el
    contador sin tener que generar una reseña primero. La arma el mismo servicio
    que usa el endpoint, así que el texto de la demo es el real."""
    existente = db.query(Notificacion).filter(Notificacion.resena_id == resena.id_resena).first()
    if existente:
        return existente
    if resena.fecha_creacion is None:
        db.refresh(resena)  # la fecha la pone la base al insertar
    return crear_notificacion_resena_nueva(db, resena, solicitud)


def run():
    preparar_esquema()
    db = SessionLocal()
    try:
        categorias = {nombre: get_or_create_categoria(db, nombre, descripcion) for nombre, descripcion in CATEGORIAS}

        oferentes = [get_or_create_oferente(db, categorias, datos) for datos in OFERENTES_DEMO]

        get_or_create_admin(db)
        padron_cargado = get_or_create_padron(db)

        # Un enlace por canal, para probar la vista de reseña sin depender del
        # correo ni de WhatsApp.
        get_or_create_solicitud(
            db,
            oferentes[0],
            CODIGO_SOLICITUD_EMAIL,
            nombre_cliente="Cliente Demo",
            email_cliente="cliente.demo@offix.example.com",
        )
        get_or_create_solicitud(
            db,
            oferentes[0],
            CODIGO_SOLICITUD_WHATSAPP,
            nombre_cliente="Cliente WhatsApp",
            telefono_cliente="3516924551",
        )
        resena = get_or_create_resena_aceptada(db, oferentes[0])

        # Una reseña pendiente con su notificación, para la campana de la demo.
        solicitud_pendiente = get_or_create_solicitud(
            db,
            oferentes[1],
            "DEMO-PENDIENTE-0001",
            nombre_cliente="Gustavo Rivas",
            telefono_cliente="3564692755",
            email_cliente="gustavo.rivas@offix.example.com",
        )
        resena_pendiente = db.query(Resena).filter(Resena.solicitud_id == solicitud_pendiente.id_solicitud).first()
        if not resena_pendiente:
            criterios = {"precio": 4.5, "calidad": 4.0, "atencion": 5.0, "puntualidad": 4.0}
            resena_pendiente = Resena(
                oferente_id=oferentes[1].id_oferente,
                solicitud_id=solicitud_pendiente.id_solicitud,
                nombre_cliente=solicitud_pendiente.nombre_cliente,
                contacto_cliente_ingresado=solicitud_pendiente.email_cliente,
                calificaciones_comentarios={
                    "puntuacion_global": round(sum(criterios.values()) / len(criterios), 2),
                    "criterios": criterios,
                    "comentario": "Resolvió una pérdida el mismo día.",
                },
                estado=EstadoResena.PENDIENTE_ACEPTACION,
            )
            solicitud_pendiente.estado = EstadoSolicitud.UTILIZADA
            db.add(resena_pendiente)
            db.flush()
        get_or_create_notificacion_pendiente(db, resena_pendiente, solicitud_pendiente)

        db.commit()
        print(f"Datos de prueba cargados/verificados correctamente ({len(categorias)} categorías, {len(oferentes)} oferentes).")
        print(f"Usuario admin: admin@offix.example.com / password: {PASSWORD_SEED}")
        print(f"Oferentes de ejemplo: password para todos: {PASSWORD_SEED}")
        print("Enlaces de reseña de demo (sin login):")
        print(f"  - canal Email:    {CODIGO_SOLICITUD_EMAIL}")
        print(f"  - canal WhatsApp: {CODIGO_SOLICITUD_WHATSAPP}")
        print(f"{oferentes[0].nombre} {oferentes[0].apellido} tiene una reseña aceptada de ejemplo en su perfil.")
        print(f"{oferentes[1].nombre} {oferentes[1].apellido} tiene 1 notificación pendiente en la campana.")
        print(f"Padrones cargados: {padron_cargado} matrículas nuevas (0 = ya estaban cargadas).")
        print(
            f"  - Gasista (completo, 68 matriculados): logueate como {oferentes[1].nombre} {oferentes[1].apellido} y validá "
            f'{{"tipo_profesional": "Gasista", "numero_matricula": "{MATRICULA_DEMO_GASISTA}"}}'
        )
        print(
            f"  - Aire acondicionado (PARCIAL, 49 de 77 — falta la página 2 del export): logueate como "
            f"{oferentes[3].nombre} {oferentes[3].apellido} y validá "
            f'{{"tipo_profesional": "Aire acondicionado", "numero_matricula": "{MATRICULA_DEMO_AIRE_ACONDICIONADO}"}}'
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()

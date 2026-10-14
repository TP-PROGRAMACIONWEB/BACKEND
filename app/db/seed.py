"""Carga datos de prueba para demostrar Sprint 1 y Sprint 2: categorías de oficios,
Oferentes de ejemplo (con su Usuario asociado y el registro completo), reseñas
aceptadas y pendientes, la notificación de la campana, los padrones de matriculados
de HU-02 y un Usuario sin registro para probar CA01.
Idempotente: se puede correr varias veces sin duplicar datos.

Uso: python -m app.db.seed
"""

from datetime import datetime, time, timedelta, timezone
from pathlib import Path

from app.core.config import settings
from app.core.security import hash_password
from app.db.database import SessionLocal, preparar_esquema
from app.models import alerta_admin, archivo_adjunto, oferente_dia_atencion, trabajo_realizado  # noqa: F401 — registran sus mappers
from app.models.categoria import Categoria
from app.models.matricula import PadronMatricula, TipoProfesionalMatricula
from app.models.notificacion import Notificacion
from app.models.oferente import EstadoVerificacion, Oferente
from app.models.oferente_dia_atencion import OferenteDiaAtencion
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

LUNES_A_VIERNES = [1, 2, 3, 4, 5]

# DNI/CUIT con dígito verificador válido (HU-04, D5) y teléfonos de 10 dígitos (D10).
OFERENTES_DEMO = [
    dict(
        email="juan.perez@offix.example.com",
        nombre="Juan Pérez",
        categoria="Electricista",
        dni_cuit="20301112220",
        telefono="3564400111",
        estado_verificacion=EstadoVerificacion.VERIFICADO,
    ),
    dict(
        email="maria.gomez@offix.example.com",
        # Nombre real del padrón de Gasistas (matrícula 1000008919), para
        # poder demostrar HU-02 de punta a punta: con un nombre inventado el
        # match contra el padrón lo rechaza.
        nombre="María Clara Alessi",
        categoria="Gasista",
        dni_cuit="27283334444",
        telefono="3564400222",
        estado_verificacion=EstadoVerificacion.VERIFICADO,
    ),
    dict(
        email="carlos.fernandez@offix.example.com",
        nombre="Carlos Fernández",
        categoria="Plomero",
        dni_cuit="20255556666",
        telefono="3564400333",
        estado_verificacion=EstadoVerificacion.PENDIENTE,
    ),
    dict(
        email="lucia.rodriguez@offix.example.com",
        # Nombre real del padrón de Aire acondicionado (matrícula 28408435),
        # igual que se hizo con la Gasista de demo: con un nombre inventado el
        # match contra el padrón la rechaza.
        nombre="Martin Abatedaga",
        categoria="Técnico en Aire Acondicionado",
        dni_cuit="27267778898",
        telefono="3564400444",
        estado_verificacion=EstadoVerificacion.VERIFICADO,
    ),
    dict(
        email="sergio.diaz@offix.example.com",
        nombre="Sergio Díaz",
        categoria="Albañil",
        dni_cuit="20319990004",
        telefono="3564400555",
        estado_verificacion=EstadoVerificacion.PENDIENTE,
    ),
    dict(
        email="ana.torres@offix.example.com",
        nombre="Ana Torres",
        categoria="Carpintero",
        dni_cuit="27292223337",
        telefono="3564400666",
        estado_verificacion=EstadoVerificacion.RECHAZADO,
    ),
    # Caso de referencia de QA (HU-04): perfil completo con guardia y sin domingos.
    dict(
        email="serena.ludena@offix.example.com",
        nombre="Serena Ludueña",
        categoria="Electricista",
        dni_cuit="27301112225",
        telefono="3564400777",
        estado_verificacion=EstadoVerificacion.PENDIENTE,
        especialidad="prueba",
        experiencia="3_A_5",
        dias=LUNES_A_VIERNES,
        disponible_emergencia=True,
        info_guardia="No domingos",
    ),
]

EMAIL_SIN_REGISTRO = "sin.registro@offix.example.com"

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


def _asegurar_dias(db, oferente: Oferente, dias: list[int]) -> None:
    """Los días se reemplazan solo si el oferente no los tiene: no pisa lo que
    haya cargado alguien desde la app."""
    if oferente.dias_atencion:
        return
    for dia in dias:
        db.add(OferenteDiaAtencion(oferente_id=oferente.id_oferente, dia=dia))


def get_or_create_oferente(db, categorias: dict[str, Categoria], datos: dict) -> Oferente:
    usuario = db.query(Usuario).filter(Usuario.email == datos["email"]).first()
    if usuario and usuario.oferente:
        # nombre, DNI y teléfono se sincronizan en cada corrida: el
        # nombre habilita el match contra el padrón (HU-02), y el DNI y el
        # teléfono tienen que quedar con el formato que valida la API.
        oferente = usuario.oferente
        oferente.nombre = datos["nombre"]
        oferente.dni_cuit = datos["dni_cuit"]
        oferente.telefono = datos["telefono"]
        _completar_registro(db, oferente, datos)
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
        dni_cuit=datos["dni_cuit"],
        telefono=datos["telefono"],
        estado_verificacion=datos["estado_verificacion"],
        descripcion=f"{datos['nombre']} — {datos['categoria']} de prueba para demo.",
    )
    db.add(oferente)
    db.flush()
    _completar_registro(db, oferente, datos)
    return oferente


def _completar_registro(db, oferente: Oferente, datos: dict) -> None:
    """Campos del formulario de Sprint 2 con valores por defecto de la demo."""
    oferente.especialidad = datos.get("especialidad", oferente.especialidad)
    oferente.experiencia = datos.get("experiencia", oferente.experiencia)
    oferente.disponible_emergencia = datos.get("disponible_emergencia", oferente.disponible_emergencia or False)
    oferente.info_guardia = datos.get("info_guardia") if oferente.disponible_emergencia else None
    oferente.hora_inicio_atencion = oferente.hora_inicio_atencion or time(8, 0)
    oferente.hora_fin_atencion = oferente.hora_fin_atencion or time(18, 0)
    _asegurar_dias(db, oferente, datos.get("dias", LUNES_A_VIERNES))


def get_or_create_usuario_sin_registro(db) -> Usuario:
    """Un Oferente que entró con email y password pero nunca completó el formulario:
    para probar CA01 (`requiere_registro = true`) sin depender de Google."""
    usuario = db.query(Usuario).filter(Usuario.email == EMAIL_SIN_REGISTRO).first()
    if usuario:
        return usuario
    usuario = Usuario(email=EMAIL_SIN_REGISTRO, password_hash=hash_password(PASSWORD_SEED), rol=RolUsuario.OFERENTE)
    db.add(usuario)
    db.flush()
    return usuario


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


def _criterios_promedio(criterios: dict) -> float:
    return round(sum(criterios.values()) / len(criterios), 2)


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
            "puntuacion_global": _criterios_promedio(criterios),
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


def get_or_create_resenas_serena(db, oferente: Oferente) -> None:
    """Dos reseñas aceptadas con fechas fijas (casos A54–A56 de QA), con valores de
    media estrella: los de A55 no se pueden reproducir por criterio."""
    datos = [
        ("DEMO-SERENA-0001", "Laura Méndez", "laura.mendez@offix.example.com", datetime(2026, 9, 25, 15, 0, tzinfo=timezone.utc),
         {"precio": 4.5, "calidad": 4.5, "atencion": 5.0, "puntualidad": 4.0}, "Llegó a horario y resolvió todo en una visita."),
        ("DEMO-SERENA-0002", "Pablo Ríos", "pablo.rios@offix.example.com", datetime(2026, 9, 29, 21, 29, tzinfo=timezone.utc),
         {"precio": 5.0, "calidad": 5.0, "atencion": 4.5, "puntualidad": 4.5}, "Buen servicio, muy claro en el presupuesto."),
    ]
    for codigo, nombre, email, fecha, criterios, comentario in datos:
        solicitud = get_or_create_solicitud(db, oferente, codigo, nombre_cliente=nombre, email_cliente=email)
        if db.query(Resena).filter(Resena.solicitud_id == solicitud.id_solicitud).first():
            continue
        resena = Resena(
            oferente_id=oferente.id_oferente,
            solicitud_id=solicitud.id_solicitud,
            nombre_cliente=nombre,
            contacto_cliente_ingresado=email,
            calificaciones_comentarios={
                "puntuacion_global": _criterios_promedio(criterios),
                "criterios": criterios,
                "comentario": comentario,
            },
            estado=EstadoResena.ACEPTADA,
            fecha_creacion=fecha,
        )
        solicitud.estado = EstadoSolicitud.UTILIZADA
        db.add(resena)
    db.flush()
    aceptadas = db.query(Resena).filter(Resena.oferente_id == oferente.id_oferente, Resena.estado == EstadoResena.ACEPTADA).all()
    oferente.promedio_calificacion = round(sum(r.calificaciones_comentarios["puntuacion_global"] for r in aceptadas) / len(aceptadas), 2)


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
        serena = oferentes[-1]

        get_or_create_admin(db)
        get_or_create_usuario_sin_registro(db)
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
        get_or_create_resena_aceptada(db, oferentes[0])
        get_or_create_resenas_serena(db, serena)

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
                    "puntuacion_global": _criterios_promedio(criterios),
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
        print(f"Caso de QA (CA01): {EMAIL_SIN_REGISTRO} tiene rol Oferente y todavía no completó el registro.")
        print(f"Perfil completo de referencia: {serena.nombre} (Lun a Vie, con guardia y dos reseñas aceptadas).")
        print("Enlaces de reseña de demo (sin login):")
        print(f"  - canal Email:    {CODIGO_SOLICITUD_EMAIL}")
        print(f"  - canal WhatsApp: {CODIGO_SOLICITUD_WHATSAPP}")
        print(f"{oferentes[0].nombre} tiene una reseña aceptada de ejemplo en su perfil.")
        print(f"{oferentes[1].nombre} tiene 1 notificación pendiente en la campana.")
        print(f"Padrones cargados: {padron_cargado} matrículas nuevas (0 = ya estaban cargadas).")
        print(
            f"  - Gasista (completo, 68 matriculados): logueate como {oferentes[1].nombre} y validá "
            f'{{"tipo_profesional": "Gasista", "numero_matricula": "{MATRICULA_DEMO_GASISTA}"}}'
        )
        print(
            f"  - Aire acondicionado (PARCIAL, 49 de 77 — falta la página 2 del export): logueate como "
            f"{oferentes[3].nombre} y validá "
            f'{{"tipo_profesional": "Aire acondicionado", "numero_matricula": "{MATRICULA_DEMO_AIRE_ACONDICIONADO}"}}'
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()

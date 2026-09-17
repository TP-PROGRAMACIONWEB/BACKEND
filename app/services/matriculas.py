"""Validación de matrícula profesional (HU-02, Fase 4).

Orquesta el flujo completo descrito en `docs/plan-sprint-1.md`: matrícula
trampa → padrón → coincidencia de nombre → vencimiento → alta / reemplazo /
ya-fidelizada, dejando el historial completo en `ValidacionMatricula` y
disparando las notificaciones de la bandeja que correspondan. Igual que
`services/resenas.py` y `services/notificaciones.py`, solo hace `flush`: el
`commit` lo hace el router.
"""

import re
import unicodedata
from datetime import date, datetime, timezone
from difflib import SequenceMatcher

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.matricula import EstadoReemplazo, Matricula, PadronMatricula, ResultadoValidacion, ValidacionMatricula
from app.models.notificacion import EstadoNotificacion, Notificacion, TipoNotificacion
from app.models.oferente import Oferente
from app.models.usuario import RolUsuario, Usuario

DIGITOS_POR_TIPO = {
    "Gasista": 10,
    # El CA01 decía 9; el padrón real (llegado 2026-09-16) trae matrículas de
    # 8 dígitos. Corregido acá y en el propio CA — ver plan, pregunta abierta #1.
    "Aire acondicionado": 8,
}

MATRICULAS_TRAMPA = {
    "Gasista": "9999999999",
    "Aire acondicionado": "99999999",
}

UMBRAL_COINCIDENCIA_NOMBRE = 0.90

# Textos literales de los criterios de aceptación de HU-02: QA los verifica tal
# cual, así que no se reescriben.
MENSAJE_CA05_VALIDADA = "Su matrícula fue fidelizada exitosamente"
MENSAJE_CA04_NO_ENCONTRADA = "Su matrícula no fue encontrada en el padrón, revise los datos y vuelva a intentarlo"
MENSAJE_CA03_TIMEOUT = "No pudimos procesar tu validación en este momento, intentá nuevamente más tarde"
MENSAJE_CA06_YA_FIDELIZADA = "Su matrícula ya fue fidelizada"

MENSAJES_RESULTADO = {
    ResultadoValidacion.VALIDADA: MENSAJE_CA05_VALIDADA,
    ResultadoValidacion.NO_ENCONTRADA: MENSAJE_CA04_NO_ENCONTRADA,
    ResultadoValidacion.TIMEOUT: MENSAJE_CA03_TIMEOUT,
    ResultadoValidacion.YA_FIDELIZADA: MENSAJE_CA06_YA_FIDELIZADA,
    # Ningún CA define estos dos casos. Por decisión del equipo se muestra el
    # texto del CA04 en vez de inventar uno: para el Profesional, en los dos la
    # matrícula no es válida y tiene que revisar los datos. El `resultado`
    # sigue distinguiéndolos, así el historial conserva el motivo real.
    ResultadoValidacion.VENCIDA: MENSAJE_CA04_NO_ENCONTRADA,
    ResultadoValidacion.NOMBRE_NO_COINCIDE: MENSAJE_CA04_NO_ENCONTRADA,
    # Sin equivalente en los CA: ninguno de sus textos describe un pedido que
    # queda esperando al Administrador. Pendiente de que QA/PM lo defina.
    ResultadoValidacion.REEMPLAZO_SOLICITADO: (
        "Tu solicitud de reemplazo de matrícula fue enviada al Administrador y está pendiente de autorización. "
        "Mientras tanto, tu matrícula anterior sigue vigente."
    ),
}

_TIPO_NOTIFICACION_POR_RESULTADO = {
    ResultadoValidacion.VALIDADA: TipoNotificacion.MATRICULA_VALIDADA,
    ResultadoValidacion.NO_ENCONTRADA: TipoNotificacion.MATRICULA_NO_ENCONTRADA,
    ResultadoValidacion.TIMEOUT: TipoNotificacion.MATRICULA_TIMEOUT,
    ResultadoValidacion.YA_FIDELIZADA: TipoNotificacion.MATRICULA_YA_FIDELIZADA,
    ResultadoValidacion.VENCIDA: TipoNotificacion.MATRICULA_VENCIDA,
    ResultadoValidacion.NOMBRE_NO_COINCIDE: TipoNotificacion.MATRICULA_NOMBRE_NO_COINCIDE,
    ResultadoValidacion.REEMPLAZO_SOLICITADO: TipoNotificacion.MATRICULA_REEMPLAZO_PENDIENTE,
}

_PUNTUACION_RE = re.compile(r"[^\w\s]", re.UNICODE)


def normalizar_texto(texto: str) -> str:
    """Mayúsculas, sin acentos, sin puntuación, espacios colapsados."""
    sin_acentos = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    sin_puntuacion = _PUNTUACION_RE.sub(" ", sin_acentos.upper())
    return " ".join(sin_puntuacion.split())


def comparar_nombres(nombre_perfil: str, nombre_padron: str) -> bool:
    """El padrón trae `APELLIDO NOMBRE(S)` en mayúsculas; el perfil, campos
    separados con acentos. Se compara como conjunto de tokens, no como
    cadena: cada token del perfil tiene que tener su par en el padrón con al
    menos 90% de similitud (`difflib.SequenceMatcher`)."""
    tokens_perfil = normalizar_texto(nombre_perfil).split()
    tokens_padron = normalizar_texto(nombre_padron).split()
    if not tokens_perfil:
        return False

    for token_perfil in tokens_perfil:
        mejor = max(
            (SequenceMatcher(None, token_perfil, token_padron).ratio() for token_padron in tokens_padron),
            default=0.0,
        )
        if mejor < UMBRAL_COINCIDENCIA_NOMBRE:
            return False
    return True


def _crear_notificacion(
    db: Session, *, usuario_id: int, tipo: str, mensaje: str, requiere_accion: bool, validacion_id: int
) -> Notificacion:
    notificacion = Notificacion(
        usuario_id=usuario_id,
        tipo=tipo,
        mensaje=mensaje,
        requiere_accion=requiere_accion,
        validacion_matricula_id=validacion_id,
    )
    db.add(notificacion)
    return notificacion


def _supersedear_reemplazos_previos(db: Session, oferente_id: int, tipo_profesional: str, excepto_id: int) -> None:
    pendientes = (
        db.query(ValidacionMatricula)
        .filter(
            ValidacionMatricula.oferente_id == oferente_id,
            ValidacionMatricula.tipo_profesional == tipo_profesional,
            ValidacionMatricula.resultado == ResultadoValidacion.REEMPLAZO_SOLICITADO,
            ValidacionMatricula.estado_reemplazo == EstadoReemplazo.PENDIENTE,
            ValidacionMatricula.id_validacion != excepto_id,
        )
        .all()
    )
    if not pendientes:
        return

    for pendiente in pendientes:
        pendiente.estado_reemplazo = EstadoReemplazo.SUPERSEDED

    # El pedido viejo ya no se puede resolver, así que sus notificaciones al
    # Administrador no pueden quedar esperando una decisión: si no, el contador
    # de su campana no baja nunca. Se cierran como Leida porque el Administrador
    # no aceptó ni rechazó nada; el pedido nuevo trae su propia notificación.
    ahora = datetime.now(timezone.utc)
    notificaciones = (
        db.query(Notificacion)
        .filter(
            Notificacion.validacion_matricula_id.in_([p.id_validacion for p in pendientes]),
            Notificacion.requiere_accion.is_(True),
            Notificacion.estado == EstadoNotificacion.PENDIENTE,
        )
        .all()
    )
    for notificacion in notificaciones:
        notificacion.estado = EstadoNotificacion.LEIDA
        notificacion.fecha_resolucion = ahora


def validar_matricula(db: Session, oferente: Oferente, tipo_profesional: str, numero_matricula: str) -> ValidacionMatricula:
    categoria_padron: str | None = None
    fecha_vencimiento_padron: date | None = None

    trampa = MATRICULAS_TRAMPA.get(tipo_profesional)
    if settings.matricula_trap_habilitada and trampa is not None and numero_matricula == trampa:
        resultado = ResultadoValidacion.TIMEOUT
    else:
        padron = (
            db.query(PadronMatricula)
            .filter(
                PadronMatricula.tipo_profesional == tipo_profesional,
                PadronMatricula.numero_matricula == numero_matricula,
            )
            .first()
        )
        if not padron:
            resultado = ResultadoValidacion.NO_ENCONTRADA
        elif not comparar_nombres(f"{oferente.nombre} {oferente.apellido}", padron.nombre_matriculado):
            resultado = ResultadoValidacion.NOMBRE_NO_COINCIDE
        elif padron.fecha_vencimiento < date.today():
            resultado = ResultadoValidacion.VENCIDA
        else:
            categoria_padron = padron.categoria
            fecha_vencimiento_padron = padron.fecha_vencimiento
            existente = (
                db.query(Matricula)
                .filter(Matricula.oferente_id == oferente.id_oferente, Matricula.tipo_profesional == tipo_profesional)
                .first()
            )
            if not existente:
                resultado = ResultadoValidacion.VALIDADA
            elif existente.numero_matricula == numero_matricula:
                resultado = ResultadoValidacion.YA_FIDELIZADA
            else:
                resultado = ResultadoValidacion.REEMPLAZO_SOLICITADO

    validacion = ValidacionMatricula(
        oferente_id=oferente.id_oferente,
        tipo_profesional=tipo_profesional,
        numero_matricula=numero_matricula,
        resultado=resultado,
        categoria_padron=categoria_padron,
        fecha_vencimiento_padron=fecha_vencimiento_padron,
        estado_reemplazo=EstadoReemplazo.PENDIENTE if resultado == ResultadoValidacion.REEMPLAZO_SOLICITADO else None,
    )
    db.add(validacion)
    db.flush()

    if resultado == ResultadoValidacion.VALIDADA:
        db.add(
            Matricula(
                oferente_id=oferente.id_oferente,
                tipo_profesional=tipo_profesional,
                numero_matricula=numero_matricula,
                categoria=categoria_padron,
                fecha_vencimiento=fecha_vencimiento_padron,
            )
        )
        _crear_notificacion(
            db,
            usuario_id=oferente.id_oferente,
            tipo=TipoNotificacion.MATRICULA_VALIDADA,
            mensaje=MENSAJES_RESULTADO[resultado],
            requiere_accion=False,
            validacion_id=validacion.id_validacion,
        )
    elif resultado == ResultadoValidacion.REEMPLAZO_SOLICITADO:
        _supersedear_reemplazos_previos(db, oferente.id_oferente, tipo_profesional, excepto_id=validacion.id_validacion)
        matricula_actual = (
            db.query(Matricula)
            .filter(Matricula.oferente_id == oferente.id_oferente, Matricula.tipo_profesional == tipo_profesional)
            .first()
        )
        nombre_oferente = f"{oferente.nombre} {oferente.apellido}"
        mensaje_admin = (
            f"{nombre_oferente} solicita reemplazar su matrícula de {tipo_profesional} "
            f"({matricula_actual.numero_matricula} → {numero_matricula}). Autorizá o denegá el cambio."
        )
        admins = db.query(Usuario).filter(Usuario.rol == RolUsuario.ADMINISTRADOR).all()
        for admin in admins:
            _crear_notificacion(
                db,
                usuario_id=admin.id_usuario,
                tipo=TipoNotificacion.MATRICULA_REEMPLAZO_SOLICITADO,
                mensaje=mensaje_admin,
                requiere_accion=True,
                validacion_id=validacion.id_validacion,
            )
        _crear_notificacion(
            db,
            usuario_id=oferente.id_oferente,
            tipo=TipoNotificacion.MATRICULA_REEMPLAZO_PENDIENTE,
            mensaje=MENSAJES_RESULTADO[resultado],
            requiere_accion=False,
            validacion_id=validacion.id_validacion,
        )
    else:
        _crear_notificacion(
            db,
            usuario_id=oferente.id_oferente,
            tipo=_TIPO_NOTIFICACION_POR_RESULTADO[resultado],
            mensaje=MENSAJES_RESULTADO[resultado],
            requiere_accion=False,
            validacion_id=validacion.id_validacion,
        )

    db.flush()
    return validacion


def resolver_reemplazo(db: Session, validacion: ValidacionMatricula, autorizar: bool) -> Matricula | None:
    """Aplica (o descarta) el reemplazo que autoriza/deniega el Administrador
    y avisa al Oferente del resultado. Devuelve la `Matricula` actualizada
    cuando se autoriza, `None` si se deniega."""
    matricula = None
    if autorizar:
        matricula = (
            db.query(Matricula)
            .filter(
                Matricula.oferente_id == validacion.oferente_id,
                Matricula.tipo_profesional == validacion.tipo_profesional,
            )
            .first()
        )
        matricula.numero_matricula = validacion.numero_matricula
        matricula.categoria = validacion.categoria_padron
        matricula.fecha_vencimiento = validacion.fecha_vencimiento_padron
        matricula.fecha_fidelizacion = datetime.now(timezone.utc)
        validacion.estado_reemplazo = EstadoReemplazo.AUTORIZADO
        mensaje = "El Administrador autorizó el reemplazo de tu matrícula. Ya está actualizada en tu perfil."
    else:
        validacion.estado_reemplazo = EstadoReemplazo.DENEGADO
        mensaje = "El Administrador no autorizó el reemplazo de tu matrícula. Se mantiene la matrícula anterior."

    _crear_notificacion(
        db,
        usuario_id=validacion.oferente_id,
        tipo=TipoNotificacion.MATRICULA_REEMPLAZO_RESUELTO,
        mensaje=mensaje,
        requiere_accion=False,
        validacion_id=validacion.id_validacion,
    )
    db.flush()
    return matricula

"""HU-01 v1.2 — Reglas de Sprint 2: contacto según quién genera el enlace, anti
auto-reseña, idempotencia, límites anti-spam, texto literal de la notificación,
salida pública y dedupe de la alerta."""

import itertools

from app.core.config import settings
from app.models.alerta_admin import AlertaAdministrador
from app.models.notificacion import Notificacion
from app.models.solicitud_resena import SolicitudResena
from app.tests.conftest import CRITERIOS_VALIDOS, crear_oferente_completo

_correos = itertools.count(1)


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _nuevo_correo():
    return f"cliente.s2.{next(_correos)}@test.com"


def _generar(client, oferente_id, token=None, **datos):
    cuerpo = {"nombre_cliente": "Juan Cliente", **datos}
    return client.post(
        f"/api/v1/oferentes/{oferente_id}/solicitudes-resena",
        json=cuerpo,
        headers=_auth(token) if token else {},
    )


def _codigos(respuesta) -> dict:
    return {error["campo"]: error["codigo"] for error in respuesta.json()["errores"]}


def _dejar_resena(client, oferente_id, token=None, **datos):
    datos = {"email_cliente": _nuevo_correo(), **datos}
    codigo = _generar(client, oferente_id, token=token, **datos).json()["codigo_unico"]
    return client.post("/api/v1/resenas", json={"codigo_unico": codigo, "calificaciones_comentarios": CRITERIOS_VALIDOS})


# --- Quién puede cargar qué (D8) --------------------------------------------


def test_anonimo_con_telefono_da_422_telefono_no_permitido(client, db_session):
    _, oferente_id = crear_oferente_completo(client, db_session, email="anon.tel@test.com", dni_cuit="20-30111222-0")

    respuesta = _generar(client, oferente_id, telefono_cliente="351-6924551", email_cliente=_nuevo_correo())

    assert respuesta.status_code == 422
    assert _codigos(respuesta) == {"telefono_cliente": "telefono_no_permitido"}
    assert db_session.query(SolicitudResena).count() == 0


def test_anonimo_sin_correo_da_422_email_requerido(client, db_session):
    _, oferente_id = crear_oferente_completo(client, db_session, email="anon.mail@test.com", dni_cuit="20-30111222-0")

    respuesta = _generar(client, oferente_id)

    assert _codigos(respuesta) == {"email_cliente": "email_requerido"}


def test_dueno_sin_ningun_contacto_da_422_contacto_requerido(client, db_session):
    token, oferente_id = crear_oferente_completo(client, db_session, email="dueno.vacio@test.com", dni_cuit="20-30111222-0")

    respuesta = _generar(client, oferente_id, token=token)

    assert respuesta.status_code == 422
    assert _codigos(respuesta) == {"telefono_cliente": "contacto_requerido"}


def test_otro_usuario_logueado_se_trata_como_anonimo(client, db_session):
    _, oferente_id = crear_oferente_completo(client, db_session, email="dueno.b@test.com", dni_cuit="20-30111222-0")
    token_otro, _ = crear_oferente_completo(client, db_session, email="otro.b@test.com", dni_cuit="20-30111223-9")

    respuesta = _generar(client, oferente_id, token=token_otro, telefono_cliente="351-6924551")

    assert _codigos(respuesta) == {"telefono_cliente": "telefono_no_permitido"}


def test_token_invalido_da_401_y_no_se_trata_como_anonimo(client, db_session):
    _, oferente_id = crear_oferente_completo(client, db_session, email="token.malo@test.com", dni_cuit="20-30111222-0")

    respuesta = _generar(client, oferente_id, token="no-es-un-jwt", email_cliente=_nuevo_correo())

    assert respuesta.status_code == 401


def test_dueno_puede_cargar_telefono_y_correo(client, db_session):
    token, oferente_id = crear_oferente_completo(client, db_session, email="dueno.ok@test.com", dni_cuit="20-30111222-0")

    respuesta = _generar(client, oferente_id, token=token, telefono_cliente="351-6924551", email_cliente=_nuevo_correo())

    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["origen"] == "Ambos"


# --- Anti auto-reseña --------------------------------------------------------


def test_no_se_puede_calificar_con_el_correo_propio(client, db_session):
    token, oferente_id = crear_oferente_completo(client, db_session, email="yo.mismo@test.com", dni_cuit="20-30111222-0")

    respuesta = _generar(client, oferente_id, token=token, email_cliente="YO.MISMO@test.com")

    assert _codigos(respuesta) == {"email_cliente": "contacto_propio"}


def test_no_se_puede_calificar_con_el_telefono_propio(client, db_session):
    token, oferente_id = crear_oferente_completo(client, db_session, email="mi.tel@test.com", dni_cuit="20-30111222-0")

    respuesta = _generar(client, oferente_id, token=token, telefono_cliente="3564-400000")

    assert _codigos(respuesta) == {"telefono_cliente": "contacto_propio"}


# --- Idempotencia y límites anti-spam ---------------------------------------


def test_mismo_correo_para_el_mismo_oferente_reenvia_el_mismo_enlace(client, db_session, emails):
    _, oferente_id = crear_oferente_completo(client, db_session, email="repite@test.com", dni_cuit="20-30111222-0")

    primera = _generar(client, oferente_id, email_cliente="repetido@test.com").json()
    segunda = _generar(client, oferente_id, email_cliente="repetido@test.com").json()

    assert primera["codigo_unico"] == segunda["codigo_unico"]
    assert db_session.query(SolicitudResena).count() == 1
    assert len(emails.enviados) == 2  # el doble clic reenvía el correo, no crea otro enlace


def test_limite_por_correo_en_24_horas(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "resena_limite_por_email_24h", 1)
    _, primero = crear_oferente_completo(client, db_session, email="p1@test.com", dni_cuit="20-30111222-0")
    _, segundo = crear_oferente_completo(client, db_session, email="p2@test.com", dni_cuit="20-30111223-9")

    assert _generar(client, primero, email_cliente="spam@test.com").status_code == 201
    respuesta = _generar(client, segundo, email_cliente="spam@test.com")

    assert respuesta.status_code == 429
    assert respuesta.json()["detail"]["codigo"] == "limite_solicitudes"


def test_limite_por_profesional_en_24_horas(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "resena_limite_por_oferente_24h", 2)
    _, oferente_id = crear_oferente_completo(client, db_session, email="tope@test.com", dni_cuit="20-30111222-0")

    assert _generar(client, oferente_id, email_cliente=_nuevo_correo()).status_code == 201
    assert _generar(client, oferente_id, email_cliente=_nuevo_correo()).status_code == 201
    respuesta = _generar(client, oferente_id, email_cliente=_nuevo_correo())

    assert respuesta.status_code == 429


# --- Registrar la reseña -----------------------------------------------------


def test_codigo_inexistente_da_400_enlace_inexistente(client):
    respuesta = client.post("/api/v1/resenas", json={"codigo_unico": "nada", "calificaciones_comentarios": CRITERIOS_VALIDOS})

    assert respuesta.status_code == 400
    assert respuesta.json()["detail"]["codigo"] == "enlace_inexistente"


def test_la_respuesta_de_la_reseña_no_expone_contacto(client, db_session):
    _, oferente_id = crear_oferente_completo(client, db_session, email="sin.contacto@test.com", dni_cuit="20-30111222-0")
    respuesta = _dejar_resena(client, oferente_id)

    assert respuesta.status_code == 201, respuesta.text
    assert "email_cliente" not in respuesta.json()
    assert "telefono_cliente" not in respuesta.json()


# --- Notificación: texto literal de QA (A34) --------------------------------


def test_notificacion_con_telefono_usa_el_texto_literal(client, db_session):
    token, oferente_id = crear_oferente_completo(client, db_session, email="lit.tel@test.com", dni_cuit="20-30111222-0")
    _dejar_resena(client, oferente_id, token=token, telefono_cliente="351-6924551")

    mensaje = db_session.query(Notificacion).one().mensaje

    assert mensaje == "Recibiste una nueva reseña de un cliente 3516924551 a través de Offix."


def test_notificacion_sin_telefono_usa_el_correo(client, db_session):
    _, oferente_id = crear_oferente_completo(client, db_session, email="lit.mail@test.com", dni_cuit="20-30111222-0")
    _dejar_resena(client, oferente_id, email_cliente="solo.correo@test.com")

    mensaje = db_session.query(Notificacion).one().mensaje

    assert mensaje == "Recibiste una nueva reseña de un cliente solo.correo@test.com a través de Offix."


# --- Moderación --------------------------------------------------------------


def test_moderar_una_reseña_ajena_da_403(client, db_session):
    _, oferente_id = crear_oferente_completo(client, db_session, email="duena@test.com", dni_cuit="20-30111222-0")
    token_otro, _ = crear_oferente_completo(client, db_session, email="intruso@test.com", dni_cuit="20-30111223-9")
    resena_id = _dejar_resena(client, oferente_id).json()["id_resena"]

    respuesta = client.patch(f"/api/v1/resenas/{resena_id}/moderar", json={"aceptar": True}, headers=_auth(token_otro))

    assert respuesta.status_code == 403


def test_moderar_dos_veces_da_400_resena_ya_moderada(client, db_session):
    token, oferente_id = crear_oferente_completo(client, db_session, email="dos.veces@test.com", dni_cuit="20-30111222-0")
    resena_id = _dejar_resena(client, oferente_id).json()["id_resena"]
    client.patch(f"/api/v1/resenas/{resena_id}/moderar", json={"aceptar": True}, headers=_auth(token))

    respuesta = client.patch(f"/api/v1/resenas/{resena_id}/moderar", json={"aceptar": False}, headers=_auth(token))

    assert respuesta.status_code == 400
    assert respuesta.json()["detail"]["codigo"] == "resena_ya_moderada"


def test_siete_rechazos_generan_una_sola_alerta_pendiente(client, db_session):
    token, oferente_id = crear_oferente_completo(client, db_session, email="alerta.uno@test.com", dni_cuit="20-30111222-0")
    resenas = [_dejar_resena(client, oferente_id).json()["id_resena"] for _ in range(7)]

    for resena_id in resenas:
        client.patch(f"/api/v1/resenas/{resena_id}/moderar", json={"aceptar": False}, headers=_auth(token))

    assert db_session.query(AlertaAdministrador).filter(AlertaAdministrador.oferente_id == oferente_id).count() == 1


# --- Pestaña Opiniones (D11, D12) -------------------------------------------


def test_opiniones_muestran_nombre_de_pila_mas_inicial(client, db_session):
    token, oferente_id = crear_oferente_completo(client, db_session, email="opiniones@test.com", dni_cuit="20-30111222-0")
    codigo = _generar(client, oferente_id, email_cliente="jcp@test.com", nombre_cliente="Juan Carlos Pérez").json()["codigo_unico"]
    resena_id = client.post(
        "/api/v1/resenas", json={"codigo_unico": codigo, "calificaciones_comentarios": CRITERIOS_VALIDOS}
    ).json()["id_resena"]
    client.patch(f"/api/v1/resenas/{resena_id}/moderar", json={"aceptar": True}, headers=_auth(token))

    opiniones = client.get(f"/api/v1/oferentes/{oferente_id}/resenas").json()

    assert opiniones[0]["cliente"] == "Juan C."
    assert opiniones[0]["puntuacion_global"] == 4.5
    assert set(opiniones[0]) == {"id_resena", "cliente", "puntuacion_global", "criterios", "comentario", "fecha_creacion"}


def test_cantidad_resenas_del_perfil_cuenta_solo_las_aceptadas(client, db_session):
    token, oferente_id = crear_oferente_completo(client, db_session, email="cuenta@test.com", dni_cuit="20-30111222-0")
    aceptada = _dejar_resena(client, oferente_id).json()["id_resena"]
    _dejar_resena(client, oferente_id)  # queda pendiente
    client.patch(f"/api/v1/resenas/{aceptada}/moderar", json={"aceptar": True}, headers=_auth(token))

    assert client.get(f"/api/v1/oferentes/{oferente_id}").json()["cantidad_resenas"] == 1

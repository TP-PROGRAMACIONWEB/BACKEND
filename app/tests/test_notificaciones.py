"""Bandeja de notificaciones (la campana) y su relación con la moderación."""

from app.models.notificacion import EstadoNotificacion, Notificacion, TipoNotificacion
from app.models.oferente import Oferente
from app.tests.conftest import CRITERIOS_VALIDOS, crear_oferente_completo

DATOS_CLIENTE = {
    "nombre_cliente": "Juan Cliente",
    "telefono_cliente": "351-6924551",
    "email_cliente": "cliente@test.com",
}


def _generar_solicitud(client, oferente_id, **datos_cliente):
    response = client.post(
        f"/api/v1/oferentes/{oferente_id}/solicitudes-resena",
        json={**DATOS_CLIENTE, **datos_cliente},
    )
    assert response.status_code == 201, response.text
    return response.json()["codigo_unico"]


def _dejar_resena(client, oferente_id, calificaciones=None, **datos_cliente):
    codigo = _generar_solicitud(client, oferente_id, **datos_cliente)
    response = client.post(
        "/api/v1/resenas",
        json={"codigo_unico": codigo, "calificaciones_comentarios": calificaciones or CRITERIOS_VALIDOS},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _crear_informativa(db_session, usuario_id, mensaje="Su matrícula fue fidelizada exitosamente") -> Notificacion:
    """Notificación de las que no esperan decisión: se cierran marcándolas leídas."""
    notificacion = Notificacion(
        usuario_id=usuario_id,
        tipo=TipoNotificacion.MATRICULA_VALIDADA,
        mensaje=mensaje,
        requiere_accion=False,
        estado=EstadoNotificacion.PENDIENTE,
    )
    db_session.add(notificacion)
    db_session.commit()
    db_session.refresh(notificacion)
    return notificacion


# --- Creación al cargar la reseña -------------------------------------------


def test_al_crear_la_resena_se_crea_la_notificacion_pendiente(client, db_session):
    token, oferente_id = crear_oferente_completo(client, db_session, email="notif1@test.com", dni_cuit="20-30000001-1")
    resena = _dejar_resena(client, oferente_id)

    bandeja = client.get("/api/v1/notificaciones", headers=_auth(token)).json()

    assert len(bandeja) == 1
    notificacion = bandeja[0]
    assert notificacion["tipo"] == "Resena_Nueva"
    assert notificacion["estado"] == "Pendiente"
    assert notificacion["requiere_accion"] is True
    assert notificacion["resena_id"] == resena["id_resena"]


def test_la_notificacion_muestra_el_contacto_y_no_el_contenido(client, db_session):
    """CA04: la tarjeta trae los datos de contacto para verificar la identidad;
    la reseña en sí no se ve hasta que se acepta."""
    token, oferente_id = crear_oferente_completo(client, db_session, email="notif2@test.com", dni_cuit="20-30000002-2")
    _dejar_resena(
        client,
        oferente_id,
        calificaciones={
            "criterios": {"precio": 1, "calidad": 1, "atencion": 1, "puntualidad": 1},
            "comentario": "Un desastre de principio a fin",
        },
    )

    notificacion = client.get("/api/v1/notificaciones", headers=_auth(token)).json()[0]

    assert notificacion["nombre_cliente"] == "Juan Cliente"
    assert notificacion["telefono_cliente"] == "3516924551"
    assert notificacion["email_cliente"] == "cliente@test.com"
    # Ni el comentario ni la puntuación aparecen por ningún lado.
    assert "desastre" not in notificacion["mensaje"]
    assert "puntuacion_global" not in notificacion
    assert "calificaciones_comentarios" not in notificacion


def test_la_fecha_es_la_de_creacion_de_la_resena(client, db_session):
    """No la de la moderación: lo pide explícitamente el caso de prueba."""
    token, oferente_id = crear_oferente_completo(client, db_session, email="notif3@test.com", dni_cuit="20-30000003-3")
    resena = _dejar_resena(client, oferente_id)

    notificacion = client.get("/api/v1/notificaciones", headers=_auth(token)).json()[0]

    assert notificacion["fecha_creacion"] == resena["fecha_creacion"]
    assert notificacion["fecha_resolucion"] is None


def test_la_bandeja_ordena_las_mas_recientes_primero(client, db_session):
    token, oferente_id = crear_oferente_completo(client, db_session, email="notif4@test.com", dni_cuit="20-30000004-4")
    primera = _dejar_resena(client, oferente_id)
    segunda = _dejar_resena(client, oferente_id)

    bandeja = client.get("/api/v1/notificaciones", headers=_auth(token)).json()

    assert [n["resena_id"] for n in bandeja] == [segunda["id_resena"], primera["id_resena"]]


def test_la_bandeja_requiere_token(client):
    assert client.get("/api/v1/notificaciones").status_code == 401
    assert client.get("/api/v1/notificaciones/contador").status_code == 401


# --- Contador de la campana --------------------------------------------------


def test_el_contador_solo_cuenta_las_del_usuario_autenticado(client, db_session):
    token_a, oferente_a = crear_oferente_completo(client, db_session, email="cont1@test.com", dni_cuit="20-30000005-5")
    token_b, oferente_b = crear_oferente_completo(client, db_session, email="cont2@test.com", dni_cuit="20-30000006-6")

    _dejar_resena(client, oferente_a)
    _dejar_resena(client, oferente_a)
    _dejar_resena(client, oferente_b)

    assert client.get("/api/v1/notificaciones/contador", headers=_auth(token_a)).json()["pendientes_de_accion"] == 2
    assert client.get("/api/v1/notificaciones/contador", headers=_auth(token_b)).json()["pendientes_de_accion"] == 1
    # Y cada uno ve solo su propia bandeja.
    assert len(client.get("/api/v1/notificaciones", headers=_auth(token_b)).json()) == 1


def test_el_contador_distingue_las_informativas_de_las_que_esperan_decision(client, db_session):
    token, oferente_id = crear_oferente_completo(client, db_session, email="cont3@test.com", dni_cuit="20-30000007-7")
    _dejar_resena(client, oferente_id)
    _crear_informativa(db_session, oferente_id)

    contador = client.get("/api/v1/notificaciones/contador", headers=_auth(token)).json()

    assert contador["pendientes_de_accion"] == 1
    assert contador["sin_leer"] == 2


def test_el_contador_baja_al_resolver_la_notificacion(client, db_session):
    token, oferente_id = crear_oferente_completo(client, db_session, email="cont4@test.com", dni_cuit="20-30000008-8")
    resena = _dejar_resena(client, oferente_id)
    assert client.get("/api/v1/notificaciones/contador", headers=_auth(token)).json()["pendientes_de_accion"] == 1

    client.patch(f"/api/v1/resenas/{resena['id_resena']}/moderar", json={"aceptar": True}, headers=_auth(token))

    assert client.get("/api/v1/notificaciones/contador", headers=_auth(token)).json()["pendientes_de_accion"] == 0


# --- Marcar leída ------------------------------------------------------------


def test_marcar_leida_una_informativa(client, db_session):
    token, oferente_id = crear_oferente_completo(client, db_session, email="leer1@test.com", dni_cuit="20-30000009-9")
    notificacion = _crear_informativa(db_session, oferente_id)

    response = client.patch(f"/api/v1/notificaciones/{notificacion.id_notificacion}/leer", headers=_auth(token))

    assert response.status_code == 200, response.text
    assert response.json()["estado"] == "Leida"
    assert response.json()["fecha_resolucion"] is not None
    assert client.get("/api/v1/notificaciones/contador", headers=_auth(token)).json()["sin_leer"] == 0


def test_no_se_puede_marcar_leida_una_que_espera_decision(client, db_session):
    token, oferente_id = crear_oferente_completo(client, db_session, email="leer2@test.com", dni_cuit="20-30000010-0")
    _dejar_resena(client, oferente_id)
    notificacion_id = client.get("/api/v1/notificaciones", headers=_auth(token)).json()[0]["id_notificacion"]

    response = client.patch(f"/api/v1/notificaciones/{notificacion_id}/leer", headers=_auth(token))

    assert response.status_code == 400
    assert "decisión" in response.json()["detail"]


def test_no_se_puede_leer_la_notificacion_de_otro(client, db_session):
    _, oferente_a = crear_oferente_completo(client, db_session, email="leer3@test.com", dni_cuit="20-30000011-1")
    token_b, _ = crear_oferente_completo(client, db_session, email="leer4@test.com", dni_cuit="20-30000012-2")
    notificacion = _crear_informativa(db_session, oferente_a)

    response = client.patch(f"/api/v1/notificaciones/{notificacion.id_notificacion}/leer", headers=_auth(token_b))

    assert response.status_code == 403


def test_marcar_leida_una_notificacion_inexistente_404(client, db_session):
    token, _ = crear_oferente_completo(client, db_session, email="leer5@test.com", dni_cuit="20-30000013-3")
    assert client.patch("/api/v1/notificaciones/9999/leer", headers=_auth(token)).status_code == 404


# --- Resolución desde la bandeja --------------------------------------------


def test_aceptar_publica_recalcula_el_promedio_y_cierra_la_notificacion(client, db_session):
    token, oferente_id = crear_oferente_completo(client, db_session, email="acepta@test.com", dni_cuit="20-30000014-4")
    resena = _dejar_resena(client, oferente_id)

    response = client.patch(f"/api/v1/resenas/{resena['id_resena']}/moderar", json={"aceptar": True}, headers=_auth(token))

    assert response.status_code == 200, response.text
    assert response.json()["estado"] == "Aceptada"
    # Se publica en el perfil...
    assert len(client.get(f"/api/v1/oferentes/{oferente_id}/resenas").json()) == 1
    # ...el promedio se recalcula...
    db_session.expire_all()
    assert float(db_session.get(Oferente, oferente_id).promedio_calificacion) == 4.5
    # ...y la notificación queda Aceptada, con su fecha de resolución.
    notificacion = client.get("/api/v1/notificaciones", headers=_auth(token)).json()[0]
    assert notificacion["estado"] == "Aceptada"
    assert notificacion["fecha_resolucion"] is not None


def test_rechazar_no_publica_no_suma_al_promedio_y_cierra_la_notificacion(client, db_session):
    token, oferente_id = crear_oferente_completo(client, db_session, email="rechaza@test.com", dni_cuit="20-30000015-5")
    aceptada = _dejar_resena(client, oferente_id)
    client.patch(f"/api/v1/resenas/{aceptada['id_resena']}/moderar", json={"aceptar": True}, headers=_auth(token))

    mala = _dejar_resena(
        client,
        oferente_id,
        calificaciones={"criterios": {"precio": 0.5, "calidad": 0.5, "atencion": 0.5, "puntualidad": 0.5}},
    )
    response = client.patch(f"/api/v1/resenas/{mala['id_resena']}/moderar", json={"aceptar": False}, headers=_auth(token))

    assert response.status_code == 200
    assert response.json()["estado"] == "Rechazada"
    # No se publica y el promedio sigue siendo el de la aceptada.
    assert len(client.get(f"/api/v1/oferentes/{oferente_id}/resenas").json()) == 1
    db_session.expire_all()
    assert float(db_session.get(Oferente, oferente_id).promedio_calificacion) == 4.5

    estados = [n["estado"] for n in client.get("/api/v1/notificaciones", headers=_auth(token)).json()]
    assert estados == ["Rechazada", "Aceptada"]


def test_el_promedio_es_el_de_todas_las_aceptadas(client, db_session):
    token, oferente_id = crear_oferente_completo(client, db_session, email="prom@test.com", dni_cuit="20-30000016-6")

    for criterios in ({"precio": 5, "calidad": 5, "atencion": 5, "puntualidad": 5}, {"precio": 4, "calidad": 4, "atencion": 4, "puntualidad": 4}):
        resena = _dejar_resena(client, oferente_id, calificaciones={"criterios": criterios})
        client.patch(f"/api/v1/resenas/{resena['id_resena']}/moderar", json={"aceptar": True}, headers=_auth(token))

    db_session.expire_all()
    assert float(db_session.get(Oferente, oferente_id).promedio_calificacion) == 4.5


def test_la_respuesta_de_moderar_expone_el_contacto_al_dueno(client, db_session):
    token, oferente_id = crear_oferente_completo(client, db_session, email="contacto@test.com", dni_cuit="20-30000017-7")
    resena = _dejar_resena(client, oferente_id)

    cuerpo = client.patch(
        f"/api/v1/resenas/{resena['id_resena']}/moderar", json={"aceptar": True}, headers=_auth(token)
    ).json()

    assert cuerpo["telefono_cliente"] == "3516924551"
    assert cuerpo["email_cliente"] == "cliente@test.com"


def test_el_listado_publico_no_expone_el_contacto(client, db_session):
    token, oferente_id = crear_oferente_completo(client, db_session, email="privado@test.com", dni_cuit="20-30000018-8")
    resena = _dejar_resena(client, oferente_id)
    client.patch(f"/api/v1/resenas/{resena['id_resena']}/moderar", json={"aceptar": True}, headers=_auth(token))

    publica = client.get(f"/api/v1/oferentes/{oferente_id}/resenas").json()[0]

    assert "telefono_cliente" not in publica
    assert "email_cliente" not in publica
    assert "contacto_cliente_ingresado" not in publica

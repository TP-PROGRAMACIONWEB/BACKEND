from datetime import datetime, timedelta, timezone
from urllib.parse import unquote

from app.models.alerta_admin import AlertaAdministrador
from app.models.solicitud_resena import SolicitudResena
from app.tests.conftest import CRITERIOS_VALIDOS, PUNTUACION_GLOBAL_ESPERADA, crear_oferente_completo

DATOS_CLIENTE = {"nombre_cliente": "Juan Cliente", "email_cliente": "cliente@test.com"}


def _generar_solicitud(client, oferente_id, **datos_cliente):
    """Genera un enlace. El endpoint es público: no lleva token."""
    response = client.post(
        f"/api/v1/oferentes/{oferente_id}/solicitudes-resena",
        json={**DATOS_CLIENTE, **datos_cliente},
    )
    assert response.status_code == 201, response.text
    return response.json()["codigo_unico"]


def _registrar_resena(client, codigo, calificaciones=None):
    return client.post(
        "/api/v1/resenas",
        json={"codigo_unico": codigo, "calificaciones_comentarios": calificaciones or CRITERIOS_VALIDOS},
    )


def _vencer_solicitud(db_session, codigo):
    solicitud = db_session.query(SolicitudResena).filter(SolicitudResena.codigo_unico == codigo).first()
    solicitud.fecha_expiracion = datetime.now(timezone.utc) - timedelta(days=1)
    db_session.commit()


# --- HU-01: generación del enlace -------------------------------------------


def test_generar_solicitud_sin_token_funciona(client, db_session):
    """El flujo es público: el botón "Calificar" está en el perfil público y lo
    puede usar tanto un cliente como el propio Profesional."""
    _, oferente_id = crear_oferente_completo(client, db_session, email="publico@test.com", dni_cuit="20-10000001-1")

    response = client.post(f"/api/v1/oferentes/{oferente_id}/solicitudes-resena", json=DATOS_CLIENTE)

    assert response.status_code == 201, response.text
    cuerpo = response.json()
    assert cuerpo["nombre_cliente"] == "Juan Cliente"
    assert cuerpo["estado"] == "Pendiente_Uso"
    assert cuerpo["url_resena"].endswith(cuerpo["codigo_unico"])


def test_generar_solicitud_oferente_inexistente_404(client):
    response = client.post("/api/v1/oferentes/9999/solicitudes-resena", json=DATOS_CLIENTE)
    assert response.status_code == 404


def test_solo_telefono_devuelve_whatsapp_url_y_no_manda_correo(client, db_session, emails):
    _, oferente_id = crear_oferente_completo(client, db_session, email="wpp@test.com", dni_cuit="20-10000002-2")

    response = client.post(
        f"/api/v1/oferentes/{oferente_id}/solicitudes-resena",
        json={"nombre_cliente": "Juan Cliente", "telefono_cliente": "351-6924551"},
    )

    assert response.status_code == 201, response.text
    cuerpo = response.json()
    assert cuerpo["origen"] == "WhatsApp"
    assert cuerpo["email_enviado"] is False
    assert emails.enviados == []
    assert cuerpo["whatsapp_url"].startswith("https://wa.me/5493516924551?text=")
    # El teléfono se guarda normalizado, sin el guión.
    assert cuerpo["telefono_cliente"] == "3516924551"


def test_solo_mail_manda_el_correo_y_no_devuelve_whatsapp_url(client, db_session, emails):
    _, oferente_id = crear_oferente_completo(client, db_session, email="mail@test.com", dni_cuit="20-10000003-3")

    response = client.post(
        f"/api/v1/oferentes/{oferente_id}/solicitudes-resena",
        json={"nombre_cliente": "Juan Cliente", "email_cliente": "juan@test.com"},
    )

    assert response.status_code == 201, response.text
    cuerpo = response.json()
    assert cuerpo["origen"] == "Email"
    assert cuerpo["whatsapp_url"] is None
    assert cuerpo["email_enviado"] is True
    assert len(emails.enviados) == 1
    correo = emails.enviados[0]
    assert correo.destinatario == "juan@test.com"
    assert "Gracias por confiar en Oferente Prueba a través de Offix." in correo.cuerpo_html
    assert cuerpo["codigo_unico"] in correo.cuerpo_html


def test_los_dos_contactos_usan_los_dos_canales(client, db_session, emails):
    _, oferente_id = crear_oferente_completo(client, db_session, email="ambos@test.com", dni_cuit="20-10000004-4")

    response = client.post(
        f"/api/v1/oferentes/{oferente_id}/solicitudes-resena",
        json={"nombre_cliente": "Juan Cliente", "telefono_cliente": "3564-692755", "email_cliente": "juan@test.com"},
    )

    assert response.status_code == 201, response.text
    cuerpo = response.json()
    assert cuerpo["origen"] == "Ambos"
    assert cuerpo["email_enviado"] is True
    assert len(emails.enviados) == 1
    assert cuerpo["whatsapp_url"].startswith("https://wa.me/5493564692755?text=")


def test_sin_ningun_contacto_422_y_no_envia_nada(client, db_session, emails):
    _, oferente_id = crear_oferente_completo(client, db_session, email="sincontacto@test.com", dni_cuit="20-10000005-5")

    response = client.post(f"/api/v1/oferentes/{oferente_id}/solicitudes-resena", json={"nombre_cliente": "Juan Cliente"})

    assert response.status_code == 422
    assert emails.enviados == []
    assert db_session.query(SolicitudResena).count() == 0


def test_sin_nombre_422(client, db_session):
    _, oferente_id = crear_oferente_completo(client, db_session, email="sinnombre@test.com", dni_cuit="20-10000006-6")

    response = client.post(f"/api/v1/oferentes/{oferente_id}/solicitudes-resena", json={"email_cliente": "juan@test.com"})

    assert response.status_code == 422


def test_telefono_con_caracteres_no_numericos_422(client, db_session):
    _, oferente_id = crear_oferente_completo(client, db_session, email="telmal@test.com", dni_cuit="20-10000007-7")

    response = client.post(
        f"/api/v1/oferentes/{oferente_id}/solicitudes-resena",
        json={"nombre_cliente": "Juan Cliente", "telefono_cliente": "351-69A4551"},
    )

    assert response.status_code == 422


def test_telefono_con_0_15_o_prefijo_pais_422(client, db_session):
    """El usuario carga código de área y línea, nada más."""
    _, oferente_id = crear_oferente_completo(client, db_session, email="telpref@test.com", dni_cuit="20-10000008-8")

    for telefono in ("0351-6924551", "351-156924551", "+543516924551"):
        response = client.post(
            f"/api/v1/oferentes/{oferente_id}/solicitudes-resena",
            json={"nombre_cliente": "Juan Cliente", "telefono_cliente": telefono},
        )
        assert response.status_code == 422, f"{telefono} debería rechazarse"


def test_correo_con_formato_invalido_422(client, db_session):
    _, oferente_id = crear_oferente_completo(client, db_session, email="mailmal@test.com", dni_cuit="20-10000009-9")

    response = client.post(
        f"/api/v1/oferentes/{oferente_id}/solicitudes-resena",
        json={"nombre_cliente": "Juan Cliente", "email_cliente": "juan-arroba-test.com"},
    )

    assert response.status_code == 422


def test_correo_con_tld_ar_es_valido(client, db_session):
    """La validación es estándar de email: `.com.ar` y `.edu.ar` se aceptan."""
    _, oferente_id = crear_oferente_completo(client, db_session, email="mailar@test.com", dni_cuit="20-10000010-0")

    response = client.post(
        f"/api/v1/oferentes/{oferente_id}/solicitudes-resena",
        json={"nombre_cliente": "Juan Cliente", "email_cliente": "juan@empresa.com.ar"},
    )

    assert response.status_code == 201, response.text


def test_whatsapp_url_lleva_el_mensaje_de_qa_con_el_link(client, db_session):
    _, oferente_id = crear_oferente_completo(client, db_session, email="texto@test.com", dni_cuit="20-10000011-1")

    response = client.post(
        f"/api/v1/oferentes/{oferente_id}/solicitudes-resena",
        json={"nombre_cliente": "Juan Cliente", "telefono_cliente": "3516924551"},
    )

    cuerpo = response.json()
    texto = unquote(cuerpo["whatsapp_url"].split("?text=", 1)[1])
    assert texto.startswith("¡Hola!")
    assert "Gracias por confiar en Oferente Prueba a través de Offix." in texto
    assert f"Calificá tu experiencia acá: {cuerpo['url_resena']}" in texto
    assert texto.endswith("¡Gracias por ser parte de Offix!")


# --- HU-01: vista del formulario --------------------------------------------


def test_ver_solicitud_devuelve_los_datos_precargados(client, db_session):
    _, oferente_id = crear_oferente_completo(client, db_session, email="vista@test.com", dni_cuit="20-10000012-2")
    codigo = _generar_solicitud(client, oferente_id, telefono_cliente="3516924551")

    response = client.get(f"/api/v1/solicitudes-resena/{codigo}")

    assert response.status_code == 200, response.text
    cuerpo = response.json()
    assert cuerpo["nombre_cliente"] == "Juan Cliente"
    assert cuerpo["telefono_cliente"] == "3516924551"
    assert cuerpo["email_cliente"] == "cliente@test.com"
    assert cuerpo["nombre_oferente"] == "Oferente Prueba"
    assert cuerpo["utilizable"] is True
    assert cuerpo["vencida"] is False


def test_ver_solicitud_codigo_inexistente_404(client):
    assert client.get("/api/v1/solicitudes-resena/no-existe").status_code == 404


def test_ver_solicitud_ya_utilizada_no_es_utilizable(client, db_session):
    _, oferente_id = crear_oferente_completo(client, db_session, email="usada@test.com", dni_cuit="20-10000013-3")
    codigo = _generar_solicitud(client, oferente_id)
    _registrar_resena(client, codigo)

    cuerpo = client.get(f"/api/v1/solicitudes-resena/{codigo}").json()
    assert cuerpo["estado"] == "Utilizada"
    assert cuerpo["utilizable"] is False


def test_ver_solicitud_vencida_queda_expirada(client, db_session):
    _, oferente_id = crear_oferente_completo(client, db_session, email="vencida@test.com", dni_cuit="20-10000014-4")
    codigo = _generar_solicitud(client, oferente_id)
    _vencer_solicitud(db_session, codigo)

    cuerpo = client.get(f"/api/v1/solicitudes-resena/{codigo}").json()
    assert cuerpo["vencida"] is True
    assert cuerpo["utilizable"] is False
    assert cuerpo["estado"] == "Expirada"


# --- HU-01: carga de la reseña ----------------------------------------------


def test_registrar_resena_toma_los_datos_de_la_solicitud(client, db_session):
    _, oferente_id = crear_oferente_completo(client, db_session, email="valido@test.com", dni_cuit="20-10000015-5")
    codigo = _generar_solicitud(client, oferente_id)

    response = _registrar_resena(client, codigo)

    assert response.status_code == 201, response.text
    cuerpo = response.json()
    assert cuerpo["estado"] == "Pendiente_Aceptacion"
    assert cuerpo["nombre_cliente"] == "Juan Cliente"
    # La puntuación global no la manda el cliente: la calcula el backend.
    assert cuerpo["calificaciones_comentarios"]["puntuacion_global"] == PUNTUACION_GLOBAL_ESPERADA
    assert cuerpo["calificaciones_comentarios"]["criterios"] == CRITERIOS_VALIDOS["criterios"]


def test_registrar_resena_codigo_invalido_400(client):
    assert _registrar_resena(client, "codigo-que-no-existe").status_code == 400


def test_registrar_resena_codigo_ya_utilizado_400(client, db_session):
    _, oferente_id = crear_oferente_completo(client, db_session, email="reuso@test.com", dni_cuit="20-10000016-6")
    codigo = _generar_solicitud(client, oferente_id)

    assert _registrar_resena(client, codigo).status_code == 201
    assert _registrar_resena(client, codigo).status_code == 400


def test_registrar_resena_con_enlace_vencido_400(client, db_session):
    _, oferente_id = crear_oferente_completo(client, db_session, email="expirado@test.com", dni_cuit="20-10000017-7")
    codigo = _generar_solicitud(client, oferente_id)
    _vencer_solicitud(db_session, codigo)

    response = _registrar_resena(client, codigo)
    assert response.status_code == 400
    assert "venció" in response.json()["detail"]


def test_registrar_resena_criterio_faltante_422(client, db_session):
    _, oferente_id = crear_oferente_completo(client, db_session, email="faltante@test.com", dni_cuit="20-10000018-8")
    codigo = _generar_solicitud(client, oferente_id)

    response = _registrar_resena(client, codigo, {"criterios": {"precio": 5, "calidad": 5, "atencion": 5}})
    assert response.status_code == 422


def test_registrar_resena_puntuacion_fuera_de_rango_422(client, db_session):
    _, oferente_id = crear_oferente_completo(client, db_session, email="rango@test.com", dni_cuit="20-10000019-9")
    codigo = _generar_solicitud(client, oferente_id)

    response = _registrar_resena(client, codigo, {"criterios": {"precio": 99, "calidad": 5, "atencion": 5, "puntualidad": 5}})
    assert response.status_code == 422


def test_registrar_resena_media_estrella_ok(client, db_session):
    """0.5 es el mínimo válido y los pasos de media estrella se aceptan."""
    _, oferente_id = crear_oferente_completo(client, db_session, email="media@test.com", dni_cuit="20-10000020-0")
    codigo = _generar_solicitud(client, oferente_id)

    response = _registrar_resena(
        client, codigo, {"criterios": {"precio": 0.5, "calidad": 1.5, "atencion": 2.5, "puntualidad": 3.5}}
    )
    assert response.status_code == 201, response.text
    assert response.json()["calificaciones_comentarios"]["puntuacion_global"] == 2.0


def test_registrar_resena_paso_invalido_422(client, db_session):
    """0.3 no es múltiplo de 0.5: la escala es de media estrella."""
    _, oferente_id = crear_oferente_completo(client, db_session, email="paso@test.com", dni_cuit="20-10000021-1")
    codigo = _generar_solicitud(client, oferente_id)

    response = _registrar_resena(client, codigo, {"criterios": {"precio": 0.3, "calidad": 5, "atencion": 5, "puntualidad": 5}})
    assert response.status_code == 422


def test_registrar_resena_puntuacion_cero_422(client, db_session):
    """El mínimo es 0.5: no se puede puntuar con cero estrellas."""
    _, oferente_id = crear_oferente_completo(client, db_session, email="cero@test.com", dni_cuit="20-10000022-2")
    codigo = _generar_solicitud(client, oferente_id)

    response = _registrar_resena(client, codigo, {"criterios": {"precio": 0, "calidad": 5, "atencion": 5, "puntualidad": 5}})
    assert response.status_code == 422


def test_registrar_resena_sin_comentario_ok(client, db_session):
    """El comentario es opcional."""
    _, oferente_id = crear_oferente_completo(client, db_session, email="sincom@test.com", dni_cuit="20-10000023-3")
    codigo = _generar_solicitud(client, oferente_id)

    response = _registrar_resena(client, codigo, {"criterios": {"precio": 5, "calidad": 5, "atencion": 5, "puntualidad": 5}})
    assert response.status_code == 201, response.text
    assert response.json()["calificaciones_comentarios"]["comentario"] is None


def test_registrar_resena_comentario_de_mas_de_200_caracteres_422(client, db_session):
    _, oferente_id = crear_oferente_completo(client, db_session, email="largo@test.com", dni_cuit="20-10000024-4")
    codigo = _generar_solicitud(client, oferente_id)

    response = _registrar_resena(
        client,
        codigo,
        {"criterios": {"precio": 5, "calidad": 5, "atencion": 5, "puntualidad": 5}, "comentario": "x" * 201},
    )
    assert response.status_code == 422


def test_registrar_resena_comentario_de_200_caracteres_ok(client, db_session):
    _, oferente_id = crear_oferente_completo(client, db_session, email="justo@test.com", dni_cuit="20-10000025-5")
    codigo = _generar_solicitud(client, oferente_id)

    response = _registrar_resena(
        client,
        codigo,
        {"criterios": {"precio": 5, "calidad": 5, "atencion": 5, "puntualidad": 5}, "comentario": "x" * 200},
    )
    assert response.status_code == 201, response.text


# --- HU-01: moderación -------------------------------------------------------


def test_moderar_resena_aceptar_ok(client, db_session):
    token, oferente_id = crear_oferente_completo(client, db_session, email="aceptar@test.com", dni_cuit="20-10000026-6")
    codigo = _generar_solicitud(client, oferente_id)
    resena_id = _registrar_resena(client, codigo).json()["id_resena"]

    response = client.patch(
        f"/api/v1/resenas/{resena_id}/moderar",
        json={"aceptar": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["estado"] == "Aceptada"


def test_moderar_resena_no_dueno_403(client, db_session):
    token, oferente_id = crear_oferente_completo(client, db_session, email="modera1@test.com", dni_cuit="20-10000027-7")
    token_otro, _ = crear_oferente_completo(client, db_session, email="modera2@test.com", dni_cuit="20-10000028-8")
    codigo = _generar_solicitud(client, oferente_id)
    resena_id = _registrar_resena(client, codigo).json()["id_resena"]

    response = client.patch(
        f"/api/v1/resenas/{resena_id}/moderar",
        json={"aceptar": True},
        headers={"Authorization": f"Bearer {token_otro}"},
    )
    assert response.status_code == 403


def test_moderar_resena_ya_moderada_400(client, db_session):
    token, oferente_id = crear_oferente_completo(client, db_session, email="moderada@test.com", dni_cuit="20-10000029-9")
    codigo = _generar_solicitud(client, oferente_id)
    resena_id = _registrar_resena(client, codigo).json()["id_resena"]

    client.patch(f"/api/v1/resenas/{resena_id}/moderar", json={"aceptar": True}, headers={"Authorization": f"Bearer {token}"})
    response = client.patch(
        f"/api/v1/resenas/{resena_id}/moderar",
        json={"aceptar": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400


def test_listar_resenas_publicas_solo_muestra_aceptadas(client, db_session):
    token, oferente_id = crear_oferente_completo(client, db_session, email="listado@test.com", dni_cuit="20-10000030-0")

    _registrar_resena(client, _generar_solicitud(client, oferente_id))

    codigo_aceptada = _generar_solicitud(client, oferente_id)
    resena_id = _registrar_resena(client, codigo_aceptada).json()["id_resena"]
    client.patch(f"/api/v1/resenas/{resena_id}/moderar", json={"aceptar": True}, headers={"Authorization": f"Bearer {token}"})

    response = client.get(f"/api/v1/oferentes/{oferente_id}/resenas")
    assert response.status_code == 200
    resultados = response.json()
    assert len(resultados) == 1
    assert resultados[0]["estado"] == "Aceptada"


def test_alerta_se_dispara_con_5_de_10_rechazos(client, db_session):
    token, oferente_id = crear_oferente_completo(client, db_session, email="alerta@test.com", dni_cuit="20-10000031-1")

    resena_ids = [_registrar_resena(client, _generar_solicitud(client, oferente_id)).json()["id_resena"] for _ in range(10)]

    for i, resena_id in enumerate(resena_ids):
        aceptar = i >= 5  # rechaza las primeras 5, acepta las últimas 5
        client.patch(
            f"/api/v1/resenas/{resena_id}/moderar",
            json={"aceptar": aceptar},
            headers={"Authorization": f"Bearer {token}"},
        )

    alertas = db_session.query(AlertaAdministrador).filter(AlertaAdministrador.oferente_id == oferente_id).all()
    assert len(alertas) == 1


def test_alerta_no_se_dispara_con_4_de_10_rechazos(client, db_session):
    token, oferente_id = crear_oferente_completo(client, db_session, email="sinalerta@test.com", dni_cuit="20-10000032-2")

    resena_ids = [_registrar_resena(client, _generar_solicitud(client, oferente_id)).json()["id_resena"] for _ in range(10)]

    for i, resena_id in enumerate(resena_ids):
        aceptar = i >= 4  # rechaza las primeras 4, acepta las últimas 6
        client.patch(
            f"/api/v1/resenas/{resena_id}/moderar",
            json={"aceptar": aceptar},
            headers={"Authorization": f"Bearer {token}"},
        )

    alertas = db_session.query(AlertaAdministrador).filter(AlertaAdministrador.oferente_id == oferente_id).all()
    assert len(alertas) == 0

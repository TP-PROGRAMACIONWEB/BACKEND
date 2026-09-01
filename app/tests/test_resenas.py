from app.models.alerta_admin import AlertaAdministrador
from app.tests.conftest import CRITERIOS_VALIDOS, crear_oferente_completo


def _generar_solicitud(client, token, oferente_id, contacto="Cliente Demo - 341-5551234"):
    response = client.post(
        f"/api/v1/oferentes/{oferente_id}/solicitudes-resena",
        json={"contacto_referencia_cliente": contacto},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201, response.text
    return response.json()["codigo_unico"]


def _registrar_resena(client, codigo, nombre="Cliente Prueba"):
    return client.post(
        "/api/v1/resenas",
        json={
            "codigo_unico": codigo,
            "nombre_cliente": nombre,
            "contacto_cliente_ingresado": "cliente@test.com",
            "calificaciones_comentarios": CRITERIOS_VALIDOS,
        },
    )


def test_generar_solicitud_ok_requiere_contacto(client, db_session):
    token, oferente_id = crear_oferente_completo(client, db_session, email="genera@test.com", dni_cuit="20-10000001-1")
    response = client.post(
        f"/api/v1/oferentes/{oferente_id}/solicitudes-resena",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


def test_generar_solicitud_no_dueno_403(client, db_session):
    token_dueno, oferente_id = crear_oferente_completo(client, db_session, email="dueno@test.com", dni_cuit="20-10000002-2")
    token_otro, _ = crear_oferente_completo(client, db_session, email="otro@test.com", dni_cuit="20-10000003-3")

    response = client.post(
        f"/api/v1/oferentes/{oferente_id}/solicitudes-resena",
        json={"contacto_referencia_cliente": "cliente"},
        headers={"Authorization": f"Bearer {token_otro}"},
    )
    assert response.status_code == 403


def test_registrar_resena_codigo_valido_ok(client, db_session):
    token, oferente_id = crear_oferente_completo(client, db_session, email="valido@test.com", dni_cuit="20-10000004-4")
    codigo = _generar_solicitud(client, token, oferente_id)

    response = _registrar_resena(client, codigo)
    assert response.status_code == 201, response.text
    assert response.json()["estado"] == "Pendiente_Aprobacion"


def test_registrar_resena_codigo_invalido_400(client):
    response = _registrar_resena(client, "codigo-que-no-existe")
    assert response.status_code == 400


def test_registrar_resena_codigo_ya_utilizado_400(client, db_session):
    token, oferente_id = crear_oferente_completo(client, db_session, email="usado@test.com", dni_cuit="20-10000005-5")
    codigo = _generar_solicitud(client, token, oferente_id)

    primera = _registrar_resena(client, codigo)
    assert primera.status_code == 201

    segunda = _registrar_resena(client, codigo)
    assert segunda.status_code == 400


def test_registrar_resena_criterio_faltante_422(client, db_session):
    token, oferente_id = crear_oferente_completo(client, db_session, email="faltante@test.com", dni_cuit="20-10000006-6")
    codigo = _generar_solicitud(client, token, oferente_id)

    response = client.post(
        "/api/v1/resenas",
        json={
            "codigo_unico": codigo,
            "nombre_cliente": "Cliente",
            "contacto_cliente_ingresado": "cliente@test.com",
            "calificaciones_comentarios": {
                "puntuacion_global": 5,
                "criterios": {"precio": 5, "calidad": 5, "atencion": 5},
            },
        },
    )
    assert response.status_code == 422


def test_registrar_resena_puntuacion_fuera_de_rango_422(client, db_session):
    token, oferente_id = crear_oferente_completo(client, db_session, email="rango@test.com", dni_cuit="20-10000007-7")
    codigo = _generar_solicitud(client, token, oferente_id)

    response = client.post(
        "/api/v1/resenas",
        json={
            "codigo_unico": codigo,
            "nombre_cliente": "Cliente",
            "contacto_cliente_ingresado": "cliente@test.com",
            "calificaciones_comentarios": {
                "puntuacion_global": 5,
                "criterios": {"precio": 99, "calidad": 5, "atencion": 5, "puntualidad": 5},
            },
        },
    )
    assert response.status_code == 422


def test_moderar_resena_aprobar_ok(client, db_session):
    token, oferente_id = crear_oferente_completo(client, db_session, email="aprobar@test.com", dni_cuit="20-10000008-8")
    codigo = _generar_solicitud(client, token, oferente_id)
    resena_id = _registrar_resena(client, codigo).json()["id_resena"]

    response = client.patch(
        f"/api/v1/resenas/{resena_id}/moderar",
        json={"aprobar": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["estado"] == "Aprobada"


def test_moderar_resena_no_dueno_403(client, db_session):
    token, oferente_id = crear_oferente_completo(client, db_session, email="modera1@test.com", dni_cuit="20-10000009-9")
    token_otro, _ = crear_oferente_completo(client, db_session, email="modera2@test.com", dni_cuit="20-10000010-0")
    codigo = _generar_solicitud(client, token, oferente_id)
    resena_id = _registrar_resena(client, codigo).json()["id_resena"]

    response = client.patch(
        f"/api/v1/resenas/{resena_id}/moderar",
        json={"aprobar": True},
        headers={"Authorization": f"Bearer {token_otro}"},
    )
    assert response.status_code == 403


def test_moderar_resena_ya_moderada_400(client, db_session):
    token, oferente_id = crear_oferente_completo(client, db_session, email="moderada@test.com", dni_cuit="20-10000011-1")
    codigo = _generar_solicitud(client, token, oferente_id)
    resena_id = _registrar_resena(client, codigo).json()["id_resena"]

    client.patch(f"/api/v1/resenas/{resena_id}/moderar", json={"aprobar": True}, headers={"Authorization": f"Bearer {token}"})
    response = client.patch(
        f"/api/v1/resenas/{resena_id}/moderar",
        json={"aprobar": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400


def test_listar_resenas_publicas_solo_muestra_aprobadas(client, db_session):
    token, oferente_id = crear_oferente_completo(client, db_session, email="listado@test.com", dni_cuit="20-10000012-2")

    codigo_pendiente = _generar_solicitud(client, token, oferente_id, contacto="pendiente")
    _registrar_resena(client, codigo_pendiente)

    codigo_aprobada = _generar_solicitud(client, token, oferente_id, contacto="aprobada")
    resena_id = _registrar_resena(client, codigo_aprobada).json()["id_resena"]
    client.patch(f"/api/v1/resenas/{resena_id}/moderar", json={"aprobar": True}, headers={"Authorization": f"Bearer {token}"})

    response = client.get(f"/api/v1/oferentes/{oferente_id}/resenas")
    assert response.status_code == 200
    resultados = response.json()
    assert len(resultados) == 1
    assert resultados[0]["estado"] == "Aprobada"


def test_alerta_se_dispara_con_5_de_10_rechazos(client, db_session):
    token, oferente_id = crear_oferente_completo(client, db_session, email="alerta@test.com", dni_cuit="20-10000013-3")

    resena_ids = []
    for i in range(10):
        codigo = _generar_solicitud(client, token, oferente_id, contacto=f"cliente-{i}")
        resena_id = _registrar_resena(client, codigo, nombre=f"Cliente {i}").json()["id_resena"]
        resena_ids.append(resena_id)

    for i, resena_id in enumerate(resena_ids):
        aprobar = i >= 5  # rechaza las primeras 5, aprueba las últimas 5
        client.patch(
            f"/api/v1/resenas/{resena_id}/moderar",
            json={"aprobar": aprobar},
            headers={"Authorization": f"Bearer {token}"},
        )

    alertas = db_session.query(AlertaAdministrador).filter(AlertaAdministrador.oferente_id == oferente_id).all()
    assert len(alertas) == 1


def test_alerta_no_se_dispara_con_4_de_10_rechazos(client, db_session):
    token, oferente_id = crear_oferente_completo(client, db_session, email="sinalerta@test.com", dni_cuit="20-10000014-4")

    resena_ids = []
    for i in range(10):
        codigo = _generar_solicitud(client, token, oferente_id, contacto=f"cliente-{i}")
        resena_id = _registrar_resena(client, codigo, nombre=f"Cliente {i}").json()["id_resena"]
        resena_ids.append(resena_id)

    for i, resena_id in enumerate(resena_ids):
        aprobar = i >= 4  # rechaza las primeras 4, aprueba las últimas 6
        client.patch(
            f"/api/v1/resenas/{resena_id}/moderar",
            json={"aprobar": aprobar},
            headers={"Authorization": f"Bearer {token}"},
        )

    alertas = db_session.query(AlertaAdministrador).filter(AlertaAdministrador.oferente_id == oferente_id).all()
    assert len(alertas) == 0

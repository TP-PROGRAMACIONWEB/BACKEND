from app.tests.conftest import PASSWORD, crear_admin_db, crear_oferente_completo, registrar_y_loguear


def _login_admin(client, db_session):
    crear_admin_db(db_session)
    response = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": PASSWORD})
    return response.json()["access_token"]


def test_admin_requiere_rol_403_si_no_admin(client, db_session):
    token = registrar_y_loguear(client, "noadmin@test.com")
    response = client.get("/api/v1/admin/usuarios", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_admin_requiere_token_401(client):
    response = client.get("/api/v1/admin/usuarios")
    assert response.status_code == 401


def test_admin_listar_usuarios_ok(client, db_session):
    token_admin = _login_admin(client, db_session)
    response = client.get("/api/v1/admin/usuarios", headers={"Authorization": f"Bearer {token_admin}"})
    assert response.status_code == 200


def test_admin_verificacion_manual_ok(client, db_session):
    token_admin = _login_admin(client, db_session)
    _, oferente_id = crear_oferente_completo(client, db_session, email="verificar@test.com", dni_cuit="20-20000001-4")

    response = client.patch(
        f"/api/v1/admin/oferentes/{oferente_id}/verificacion",
        params={"estado_verificacion": "Verificado"},
        headers={"Authorization": f"Bearer {token_admin}"},
    )
    assert response.status_code == 200
    assert response.json()["estado_verificacion"] == "Verificado"


def test_admin_suspender_usuario_ok(client, db_session):
    token_admin = _login_admin(client, db_session)
    token_usuario = registrar_y_loguear(client, "suspender@test.com")

    from jose import jwt

    from app.core.config import settings

    payload = jwt.decode(token_usuario, settings.secret_key, algorithms=[settings.algorithm])
    usuario_id = int(payload["sub"])

    response = client.patch(
        f"/api/v1/admin/usuarios/{usuario_id}/estado",
        params={"estado": "Suspendida"},
        headers={"Authorization": f"Bearer {token_admin}"},
    )
    assert response.status_code == 200
    assert response.json()["estado_cuenta"] == "Suspendida"

    login_bloqueado = client.post("/api/v1/auth/login", json={"email": "suspender@test.com", "password": "Test1234!"})
    assert login_bloqueado.status_code == 403


def test_token_emitido_antes_de_bloquear_deja_de_servir_al_instante(client, db_session):
    token_admin = _login_admin(client, db_session)
    token_usuario = registrar_y_loguear(client, "bloqueo-token@test.com")
    cabecera = {"Authorization": f"Bearer {token_usuario}"}
    assert client.get("/api/v1/auth/me", headers=cabecera).status_code == 200

    from jose import jwt

    from app.core.config import settings

    usuario_id = int(jwt.decode(token_usuario, settings.secret_key, algorithms=[settings.algorithm])["sub"])
    cambio = client.patch(
        f"/api/v1/admin/usuarios/{usuario_id}/estado",
        params={"estado": "Bloqueada"},
        headers={"Authorization": f"Bearer {token_admin}"},
    )
    assert cambio.status_code == 200

    # El token viejo todavía no venció, pero la cuenta ya no está activa.
    respuesta = client.get("/api/v1/auth/me", headers=cabecera)
    assert respuesta.status_code == 401
    assert respuesta.json()["detail"] == "La cuenta no está activa"


def test_al_reactivar_el_login_emite_un_token_nuevo_que_sirve(client, db_session):
    token_admin = _login_admin(client, db_session)
    registrar_y_loguear(client, "reactivar@test.com")
    cabecera_admin = {"Authorization": f"Bearer {token_admin}"}

    from jose import jwt

    from app.core.config import settings

    token_viejo = client.post("/api/v1/auth/login", json={"email": "reactivar@test.com", "password": PASSWORD}).json()["access_token"]
    usuario_id = int(jwt.decode(token_viejo, settings.secret_key, algorithms=[settings.algorithm])["sub"])
    client.patch(f"/api/v1/admin/usuarios/{usuario_id}/estado", params={"estado": "Bloqueada"}, headers=cabecera_admin)
    client.patch(f"/api/v1/admin/usuarios/{usuario_id}/estado", params={"estado": "Activa"}, headers=cabecera_admin)

    token_nuevo = client.post("/api/v1/auth/login", json={"email": "reactivar@test.com", "password": PASSWORD}).json()["access_token"]
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_nuevo}"}).status_code == 200

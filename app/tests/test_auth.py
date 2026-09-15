from app.models.usuario import EstadoCuenta, Usuario
from app.tests.conftest import PASSWORD, crear_admin_db, registrar_y_loguear


def test_registro_ok(client):
    response = client.post("/api/v1/auth/registro", json={"email": "nuevo@test.com", "password": PASSWORD})
    assert response.status_code == 201
    assert response.json()["email"] == "nuevo@test.com"


def test_registro_email_duplicado_409(client):
    client.post("/api/v1/auth/registro", json={"email": "dup@test.com", "password": PASSWORD})
    response = client.post("/api/v1/auth/registro", json={"email": "dup@test.com", "password": PASSWORD})
    assert response.status_code == 409


def test_login_ok(client):
    client.post("/api/v1/auth/registro", json={"email": "login@test.com", "password": PASSWORD})
    response = client.post("/api/v1/auth/login", json={"email": "login@test.com", "password": PASSWORD})
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_password_incorrecta_401(client):
    client.post("/api/v1/auth/registro", json={"email": "mal@test.com", "password": PASSWORD})
    response = client.post("/api/v1/auth/login", json={"email": "mal@test.com", "password": "otra-password"})
    assert response.status_code == 401


def test_login_email_inexistente_401(client):
    response = client.post("/api/v1/auth/login", json={"email": "no-existe@test.com", "password": PASSWORD})
    assert response.status_code == 401


def test_login_cuenta_suspendida_403(client, db_session):
    client.post("/api/v1/auth/registro", json={"email": "suspendido@test.com", "password": PASSWORD})
    usuario = db_session.query(Usuario).filter(Usuario.email == "suspendido@test.com").first()
    usuario.estado_cuenta = EstadoCuenta.SUSPENDIDA
    db_session.commit()

    response = client.post("/api/v1/auth/login", json={"email": "suspendido@test.com", "password": PASSWORD})
    assert response.status_code == 403


def test_logout_sin_token_401(client):
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 401


def test_logout_con_token_204(client):
    token = registrar_y_loguear(client, "logout@test.com")
    response = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 204


def test_admin_login_ok(client, db_session):
    crear_admin_db(db_session)
    response = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": PASSWORD})
    assert response.status_code == 200


def test_los_emails_del_seed_son_validos_para_la_api(client):
    """Regresión: los mails del seed tienen que pasar la validación de EmailStr.

    Con el dominio `.test` (TLD reservado) `email-validator` los rechazaba con
    422, así que ningún usuario cargado por el seed podía iniciar sesión, que es
    justamente para lo que están. Se importan desde el seed para que los dos no
    se desincronicen.
    """
    from app.db.seed import OFERENTES_DEMO

    for datos in OFERENTES_DEMO:
        registro = client.post("/api/v1/auth/registro", json={"email": datos["email"], "password": PASSWORD})
        assert registro.status_code == 201, f"{datos['email']} rechazado: {registro.text}"

        login = client.post("/api/v1/auth/login", json={"email": datos["email"], "password": PASSWORD})
        assert login.status_code == 200, f"{datos['email']} no pudo loguearse: {login.text}"

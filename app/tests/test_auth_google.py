"""Login con Google vía Auth0 (HU-03, CA01-CA04). Convive con el login por
email/password: ninguno de los dos toca al otro."""

from urllib.parse import parse_qs, urlparse

from app.core.config import settings
from app.models.usuario import EstadoCuenta, RolUsuario, Usuario
from app.services.auth0 import Auth0ServiceFakeFalla, PerfilGoogle, get_auth0_service
from app.tests.conftest import crear_admin_db


def _iniciar_login(client):
    return client.get("/api/v1/auth/google/login", follow_redirects=False)


def _callback(client, code="un-codigo", state=None):
    if state is None:
        state = _state_de(_iniciar_login(client))
    return client.get(f"/api/v1/auth/google/callback?code={code}&state={state}", follow_redirects=False)


def _state_de(respuesta_login):
    return respuesta_login.cookies.get("oauth_state")


# --- CA01: pantalla de login / arranque del flujo ---------------------------


def test_google_login_redirige_a_auth0_con_connection_google(client):
    respuesta = _iniciar_login(client)

    assert respuesta.status_code == 302
    destino = urlparse(respuesta.headers["location"])
    assert destino.hostname == "offix-test.us.auth0.com"
    assert destino.path == "/authorize"
    query = parse_qs(destino.query)
    assert query["connection"] == ["google-oauth2"]
    assert query["client_id"] == ["client-id-test"]
    assert query["redirect_uri"] == [settings.auth0_callback_url]
    assert "state" in query


def test_google_login_pone_la_cookie_de_state(client):
    respuesta = _iniciar_login(client)
    assert respuesta.cookies.get("oauth_state") is not None


def test_google_login_sin_auth0_configurado_da_503(client, monkeypatch):
    monkeypatch.setattr(settings, "auth0_client_secret", "")
    respuesta = _iniciar_login(client)
    assert respuesta.status_code == 503


# --- CA02: autenticación exitosa --------------------------------------------


def test_callback_exitoso_redirige_a_la_vista_de_perfil_con_token(client, db_session):
    login = _iniciar_login(client)
    state = _state_de(login)

    respuesta = _callback(client, code="codigo-valido", state=state)

    assert respuesta.status_code == 302
    destino = urlparse(respuesta.headers["location"])
    assert destino.path == "/auth/callback"
    token = parse_qs(destino.query)["token"][0]

    # El JWT es el mismo formato que el de /login: sirve contra cualquier endpoint protegido.
    perfil = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert perfil.status_code == 200
    assert perfil.json() == {
        "id_usuario": perfil.json()["id_usuario"],
        "email": "cliente.google@test.com",
        "nombre": "Cliente Google",
        "rol": "Oferente",
    }


def test_primer_login_con_google_crea_el_usuario_como_oferente(client, db_session):
    _callback(client)

    usuario = db_session.query(Usuario).filter(Usuario.email == "cliente.google@test.com").first()
    assert usuario is not None
    assert usuario.rol == RolUsuario.OFERENTE
    assert usuario.nombre == "Cliente Google"
    assert usuario.estado_cuenta == EstadoCuenta.ACTIVA


def test_segundo_login_con_google_no_duplica_la_cuenta(client, db_session):
    _callback(client)
    _callback(client)

    cantidad = db_session.query(Usuario).filter(Usuario.email == "cliente.google@test.com").count()
    assert cantidad == 1


def test_login_con_google_actualiza_el_nombre_si_cambio_en_google(client, db_session):
    _callback(client)  # crea con "Cliente Google"

    from app.main import app

    state = _state_de(_iniciar_login(client))
    app.dependency_overrides[get_auth0_service] = lambda: _FakeConNombre("Cliente Renombrado")
    try:
        _callback(client, state=state)
    finally:
        del app.dependency_overrides[get_auth0_service]

    usuario = db_session.query(Usuario).filter(Usuario.email == "cliente.google@test.com").first()
    assert usuario.nombre == "Cliente Renombrado"


class _FakeConNombre:
    def __init__(self, nombre):
        self._perfil = PerfilGoogle(email="cliente.google@test.com", nombre=nombre)

    def obtener_perfil(self, code):
        return self._perfil


def test_usuario_de_google_no_puede_loguearse_despues_con_password(client, db_session):
    """La cuenta se crea con un hash de una contraseña aleatoria: nadie la conoce."""
    _callback(client)

    respuesta = client.post("/api/v1/auth/login", json={"email": "cliente.google@test.com", "password": "cualquiera"})
    assert respuesta.status_code == 401


def test_login_con_google_de_un_usuario_ya_registrado_por_password_reutiliza_la_cuenta(client, db_session):
    """Mismo mail, distinto canal de login: es la misma cuenta, no una duplicada."""
    client.post("/api/v1/auth/registro", json={"email": "cliente.google@test.com", "password": "Test1234!"})

    _callback(client)

    assert db_session.query(Usuario).filter(Usuario.email == "cliente.google@test.com").count() == 1
    # Y sigue pudiendo entrar por password, porque el login con Google no la tocó.
    assert client.post(
        "/api/v1/auth/login", json={"email": "cliente.google@test.com", "password": "Test1234!"}
    ).status_code == 200


# --- CA03: autenticación fallida ---------------------------------------------


def test_callback_sin_state_valido_redirige_al_login_con_error(client, db_session):
    respuesta = client.get("/api/v1/auth/google/callback?code=algo&state=un-state-que-no-coincide", follow_redirects=False)

    assert respuesta.status_code == 302
    destino = urlparse(respuesta.headers["location"])
    assert destino.path == "/login"
    assert parse_qs(destino.query)["error"] == ["auth_failed"]
    assert db_session.query(Usuario).count() == 0


def test_callback_con_error_de_auth0_no_crea_usuario_y_redirige_a_login(client, db_session):
    login = _iniciar_login(client)
    respuesta = client.get(
        f"/api/v1/auth/google/callback?error=access_denied&state={_state_de(login)}", follow_redirects=False
    )

    destino = urlparse(respuesta.headers["location"])
    assert destino.path == "/login"
    assert parse_qs(destino.query)["error"] == ["auth_failed"]
    assert db_session.query(Usuario).count() == 0


def test_callback_cuando_auth0_rechaza_el_intercambio_redirige_a_login(client, db_session):
    from app.main import app

    login = _iniciar_login(client)
    app.dependency_overrides[get_auth0_service] = lambda: Auth0ServiceFakeFalla()
    try:
        respuesta = client.get(
            f"/api/v1/auth/google/callback?code=malo&state={_state_de(login)}", follow_redirects=False
        )
    finally:
        del app.dependency_overrides[get_auth0_service]

    destino = urlparse(respuesta.headers["location"])
    assert destino.path == "/login"
    assert parse_qs(destino.query)["error"] == ["auth_failed"]
    assert db_session.query(Usuario).count() == 0


def test_callback_con_cuenta_suspendida_redirige_a_login_sin_token(client, db_session):
    admin = crear_admin_db(db_session, email="cliente.google@test.com")
    admin.estado_cuenta = EstadoCuenta.SUSPENDIDA
    db_session.commit()

    respuesta = _callback(client)

    destino = urlparse(respuesta.headers["location"])
    assert destino.path == "/login"
    assert parse_qs(destino.query)["error"] == ["auth_failed"]


def test_callback_no_redirige_nunca_a_la_vista_de_perfil_en_una_falla(client, db_session):
    respuesta = client.get("/api/v1/auth/google/callback?error=access_denied&state=x", follow_redirects=False)
    assert urlparse(respuesta.headers["location"]).path != settings.google_login_ruta_exito


# --- /me ----------------------------------------------------------------


def test_me_requiere_autenticacion(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_de_un_usuario_de_password_no_tiene_nombre(client):
    client.post("/api/v1/auth/registro", json={"email": "solopass@test.com", "password": "Test1234!"})
    token = client.post("/api/v1/auth/login", json={"email": "solopass@test.com", "password": "Test1234!"}).json()[
        "access_token"
    ]

    perfil = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert perfil["email"] == "solopass@test.com"
    assert perfil["nombre"] is None

import os

# La suite corre siempre sobre SQLite en memoria, aunque el .env apunte a la base
# en la nube: la variable de entorno le gana al .env, y tiene que estar antes de
# importar la app porque el engine y el schema de las tablas se deciden al
# importar `app.db.database`.
os.environ["DATABASE_URL"] = "sqlite://"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.categoria import Categoria  # noqa: E402
from app.models.usuario import RolUsuario, Usuario  # noqa: E402
from app.services.auth0 import Auth0ServiceFake, get_auth0_service  # noqa: E402
from app.services.email import EmailServiceFake, get_email_service  # noqa: E402

TEST_DATABASE_URL = "sqlite://"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture()
def db_session():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def emails() -> EmailServiceFake:
    """Doble del servicio de correo: la suite nunca manda un mail real."""
    return EmailServiceFake()


@pytest.fixture()
def auth0() -> Auth0ServiceFake:
    """Doble del login con Google: la suite nunca llama a Auth0 de verdad."""
    return Auth0ServiceFake()


@pytest.fixture()
def client(db_session, emails, auth0, monkeypatch):
    def override_get_db():
        yield db_session

    # El login con Google se prueba con settings.auth0_habilitado en True: los
    # tests que verifican el 503 lo desactivan explícitamente con monkeypatch.
    monkeypatch.setattr(settings, "auth0_domain", "offix-test.us.auth0.com")
    monkeypatch.setattr(settings, "auth0_client_id", "client-id-test")
    monkeypatch.setattr(settings, "auth0_client_secret", "client-secret-test")

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_email_service] = lambda: emails
    app.dependency_overrides[get_auth0_service] = lambda: auth0
    # El evento de startup real de la app corre create_all contra el engine de
    # producción (Postgres/SQLite del .env) — en tests las tablas ya se crean
    # contra el engine de test en la fixture db_session, así que se desactiva
    # para no intentar conectar a una base que puede no existir en este entorno.
    startup_handlers = list(app.router.on_startup)
    app.router.on_startup.clear()
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.router.on_startup.extend(startup_handlers)
        app.dependency_overrides.clear()


PASSWORD = "Test1234!"


def registrar_y_loguear(client, email: str) -> str:
    client.post("/api/v1/auth/registro", json={"email": email, "password": PASSWORD})
    response = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    return response.json()["access_token"]


def crear_categoria_db(db_session, nombre: str = "Electricista") -> Categoria:
    categoria = Categoria(nombre=nombre, descripcion="Categoría de prueba")
    db_session.add(categoria)
    db_session.commit()
    db_session.refresh(categoria)
    return categoria


def crear_admin_db(db_session, email: str = "admin@test.com") -> Usuario:
    admin = Usuario(email=email, password_hash=hash_password(PASSWORD), rol=RolUsuario.ADMINISTRADOR)
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


def crear_oferente_completo(client, db_session, email: str = "oferente@test.com", dni_cuit: str = "20-11111111-1"):
    """Registra un usuario, loguea y crea su perfil de Oferente. Devuelve (token, oferente_id)."""
    token = registrar_y_loguear(client, email)
    categoria = crear_categoria_db(db_session, nombre=f"Categoria-{email}")
    response = client.post(
        "/api/v1/oferentes",
        json={
            "nombre": "Oferente",
            "apellido": "Prueba",
            "dni_cuit": dni_cuit,
            "telefono": "+54 3564 400000",
            "categoria_id": categoria.id_categoria,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201, response.text
    oferente_id = response.json()["id_oferente"]
    return token, oferente_id


# Promedio de los cuatro criterios = 4.5, que es la puntuación global esperada.
CRITERIOS_VALIDOS = {
    "criterios": {"precio": 4, "calidad": 5, "atencion": 4.5, "puntualidad": 4.5},
    "comentario": "Excelente trabajo",
}
PUNTUACION_GLOBAL_ESPERADA = 4.5

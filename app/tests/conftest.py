import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.db.database import Base, get_db
from app.main import app
from app.models.categoria import Categoria
from app.models.usuario import RolUsuario, Usuario

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
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
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


CRITERIOS_VALIDOS = {
    "puntuacion_global": 5,
    "criterios": {"precio": 5, "calidad": 5, "atencion": 5, "puntualidad": 5},
    "comentario": "Excelente trabajo",
}

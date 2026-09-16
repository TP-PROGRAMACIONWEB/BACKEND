"""Conexión a la base de datos.

Dos variantes, elegidas por `DATABASE_URL`:

- **SQLite local** (`sqlite:///./offix_dev.db`), para desarrollo y pruebas sin
  depender de la red. Es el valor por defecto si no hay `.env`.
- **PostgreSQL en la nube** (Supabase), para el despliegue. Se acepta la URI tal
  cual la copia el panel de Supabase (`postgresql://...` o `postgres://...`).

En Postgres todas las tablas viven en un schema propio (`DATABASE_SCHEMA`,
`offix` por defecto), separado de `public`, donde está materializado el DER
original de la PM. Ese schema se crea y se modifica **solo con migraciones de
Alembic** (`migrations/`); nunca con `create_all`. SQLite no tiene schemas: ahí
las tablas se crean directo con `create_all`.
"""

from sqlalchemy import MetaData, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

HOSTS_LOCALES = {"localhost", "127.0.0.1", "::1"}


def normalizar_url(database_url: str) -> str:
    """Fuerza el driver psycopg2 para las URIs de Postgres: Supabase entrega
    `postgresql://` (o `postgres://`, que SQLAlchemy 2 ya no reconoce)."""
    for prefijo in ("postgres://", "postgresql://"):
        if database_url.startswith(prefijo):
            return "postgresql+psycopg2://" + database_url[len(prefijo) :]
    return database_url


def _opciones_engine(database_url: str) -> dict:
    url = make_url(database_url)

    if es_sqlite(database_url):
        return {"connect_args": {"check_same_thread": False}}

    connect_args = {}
    # Supabase exige SSL. Si la URI no lo pide explícitamente, se exige igual
    # para cualquier host que no sea local.
    if "sslmode" not in url.query and url.host not in HOSTS_LOCALES:
        connect_args["sslmode"] = "require"

    return {
        "connect_args": connect_args,
        # El pooler de Supabase corta conexiones ociosas: se reciclan antes de
        # que eso pase y se verifican antes de usarlas.
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }


def es_sqlite(database_url: str) -> bool:
    return make_url(database_url).get_backend_name() == "sqlite"


def schema_para(database_url: str) -> str | None:
    """El schema donde van las tablas: el configurado en Postgres, ninguno en SQLite."""
    return None if es_sqlite(database_url) else settings.database_schema


DATABASE_URL = normalizar_url(settings.database_url)
DATABASE_SCHEMA = schema_para(DATABASE_URL)

engine = create_engine(DATABASE_URL, **_opciones_engine(DATABASE_URL))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Con el schema en el MetaData, todas las tablas y sus FK quedan calificadas
# (`offix.usuarios`), sin tocar cada modelo.
Base = declarative_base(metadata=MetaData(schema=DATABASE_SCHEMA))


def preparar_esquema() -> None:
    """Crea las tablas en SQLite. En Postgres no hace nada a propósito: ahí el
    esquema lo manejan las migraciones, y un `create_all` crearía tablas que
    Alembic no conoce y rompería la siguiente migración."""
    if es_sqlite(DATABASE_URL):
        Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

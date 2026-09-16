"""Conexión a la base de datos.

Dos variantes, elegidas por `DATABASE_URL`:

- **SQLite local** (`sqlite:///./offix_dev.db`), para desarrollo y pruebas sin
  depender de la red. Es el valor por defecto si no hay `.env`.
- **PostgreSQL en la nube** (Supabase), para el despliegue. Se acepta la URI tal
  cual la copia el panel de Supabase (`postgresql://...` o `postgres://...`).
"""

from sqlalchemy import create_engine
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

    if url.get_backend_name() == "sqlite":
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


DATABASE_URL = normalizar_url(settings.database_url)

engine = create_engine(DATABASE_URL, **_opciones_engine(DATABASE_URL))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

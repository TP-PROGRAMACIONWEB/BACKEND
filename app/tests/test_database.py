"""Selección de la variante de base de datos a partir de DATABASE_URL."""

from app.db.database import _opciones_engine, normalizar_url

URI_SUPABASE = "postgresql://postgres.abc:clave%24%23@aws-0-us-east-2.pooler.supabase.com:5432/postgres"


def test_la_uri_de_supabase_se_normaliza_al_driver_psycopg2():
    assert normalizar_url(URI_SUPABASE).startswith("postgresql+psycopg2://postgres.abc:")


def test_el_alias_postgres_tambien_se_acepta():
    assert normalizar_url("postgres://u:p@host/db") == "postgresql+psycopg2://u:p@host/db"


def test_sqlite_no_se_modifica():
    assert normalizar_url("sqlite:///./offix_dev.db") == "sqlite:///./offix_dev.db"


def test_sqlite_no_usa_ssl_ni_pool_de_red():
    opciones = _opciones_engine("sqlite:///./offix_dev.db")
    assert opciones == {"connect_args": {"check_same_thread": False}}


def test_postgres_remoto_exige_ssl():
    opciones = _opciones_engine(normalizar_url(URI_SUPABASE))
    assert opciones["connect_args"] == {"sslmode": "require"}
    assert opciones["pool_pre_ping"] is True


def test_postgres_local_no_fuerza_ssl():
    assert _opciones_engine("postgresql+psycopg2://u:p@localhost:5432/offix")["connect_args"] == {}


def test_un_sslmode_explicito_en_la_uri_se_respeta():
    opciones = _opciones_engine(normalizar_url(URI_SUPABASE) + "?sslmode=verify-full")
    assert "sslmode" not in opciones["connect_args"]

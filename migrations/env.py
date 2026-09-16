"""Entorno de Alembic.

Las migraciones son **la única vía** para crear o modificar las tablas en
Postgres. Todo vive en el schema `DATABASE_SCHEMA` (`offix`): la tabla de
versiones de Alembic también, y el autogenerate ignora cualquier otro schema.
Eso es lo que protege a `public`, donde está materializado el DER original de la
PM: sin ese filtro, el autogenerate propondría borrar sus tablas porque no
aparecen en los modelos.

Uso: migrar_bd.bat, o `alembic upgrade head` con el venv activo.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import text

from app.db.database import DATABASE_SCHEMA, DATABASE_URL, Base, engine, es_sqlite
from app.main import app  # noqa: F401 — importa todos los modelos y los registra en Base.metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _incluir_nombre(name, type_, parent_names):
    """El autogenerate solo mira el schema del backend."""
    if type_ == "schema":
        return name == DATABASE_SCHEMA
    return True


def run_migrations_offline() -> None:
    """Genera el SQL sin conectarse (`alembic upgrade head --sql`), útil para
    que la PM revise el cambio antes de aplicarlo."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        include_name=_incluir_nombre,
        version_table_schema=DATABASE_SCHEMA,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    if es_sqlite(DATABASE_URL):
        raise SystemExit(
            "Las migraciones son para PostgreSQL. La base SQLite local se crea sola al "
            "levantar el backend o al correr el seed: no hace falta migrarla."
        )

    with engine.connect() as connection:
        # El schema tiene que existir antes de que Alembic cree su tabla de versiones en él.
        connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{DATABASE_SCHEMA}"'))
        connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            include_name=_incluir_nombre,
            version_table_schema=DATABASE_SCHEMA,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

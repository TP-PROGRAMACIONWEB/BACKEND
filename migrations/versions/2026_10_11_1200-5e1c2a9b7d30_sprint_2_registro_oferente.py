"""Sprint 2: registro de Oferente, trabajos realizados y límites anti-spam

Revision ID: 5e1c2a9b7d30
Revises: db8e00ae811e
Create Date: 2026-10-11 12:00:00

Cambios (ver docs/plan-sprint-2.md, "Cambios de esquema"):

- OFERENTE: especialidad, experiencia (código del catálogo) e info_guardia.
  El nombre y el apellido pasan a un solo campo, `nombre` (nombre completo o razón
  social): `apellido` se une a `nombre` y la columna se elimina.
- OFERENTE_DIAS_ATENCION (nueva): días de atención, ISO 1 a 7.
- TRABAJOS_REALIZADOS (nueva) y ARCHIVOS_ADJUNTOS: fotos de perfil, portada y
  trabajos en Supabase Storage. `url_archivo` pasa a `storage_path`.
- RESENAS: UNIQUE(solicitud_id), que cierra la carrera de doble envío.
- SOLICITUDES_RESENA: índice (email_cliente, fecha_generacion) para los límites.

Normalización de datos (solo filas existentes):

- DNI/CUIT y teléfono quedan solo con dígitos. El teléfono pierde el +54.
- Oferentes sin días de atención: lunes a viernes.
- Horarios vacíos: 08:00 a 18:00.

No se corrige el dígito verificador de los CUIT del seed: eso lo hace el seed
nuevo. La validación corre sobre lo que entra por la API, no sobre lo guardado.

Solo se ejecuta en PostgreSQL: `env.py` rechaza SQLite. Por eso la normalización
va en SQL puro: así `alembic upgrade --sql` genera el script completo para revisar.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5e1c2a9b7d30"
down_revision: Union[str, None] = "db8e00ae811e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "offix"

# Solo dígitos. Si el resultado empieza con 54 y tiene más de 10, se quita el
# prefijo de país (el +54 que se cargaba en Sprint 1).
NORMALIZAR_DNI = "UPDATE offix.oferentes SET dni_cuit = regexp_replace(dni_cuit, '[^0-9]', '', 'g')"

NORMALIZAR_TELEFONO = """
UPDATE offix.oferentes
SET telefono = CASE
    WHEN length(regexp_replace(telefono, '[^0-9]', '', 'g')) > 10
         AND regexp_replace(telefono, '[^0-9]', '', 'g') LIKE '54%'
        THEN substr(regexp_replace(telefono, '[^0-9]', '', 'g'), 3)
    ELSE regexp_replace(telefono, '[^0-9]', '', 'g')
END
"""

HORARIOS_POR_DEFECTO = """
UPDATE offix.oferentes SET hora_inicio_atencion = '08:00' WHERE hora_inicio_atencion IS NULL;
UPDATE offix.oferentes SET hora_fin_atencion = '18:00' WHERE hora_fin_atencion IS NULL
"""

# Nombre y apellido en un solo campo. Se une antes de borrar la columna, así no se
# pierde ningún dato (si la unión supera 150 caracteres, se recorta).
UNIR_NOMBRE_Y_APELLIDO = "UPDATE offix.oferentes SET nombre = left(trim(nombre || ' ' || apellido), 150)"

DIAS_LABORABLES_POR_DEFECTO = """
INSERT INTO offix.oferente_dias_atencion (oferente_id, dia)
SELECT o.id_oferente, d.dia
FROM offix.oferentes AS o
CROSS JOIN (VALUES (1), (2), (3), (4), (5)) AS d(dia)
WHERE NOT EXISTS (
    SELECT 1 FROM offix.oferente_dias_atencion AS x WHERE x.oferente_id = o.id_oferente
)
"""


def upgrade() -> None:
    # --- OFERENTE -----------------------------------------------------------
    op.execute(UNIR_NOMBRE_Y_APELLIDO)
    op.drop_column("oferentes", "apellido", schema=SCHEMA)
    op.alter_column("oferentes", "nombre", type_=sa.String(length=150), schema=SCHEMA)
    op.add_column("oferentes", sa.Column("especialidad", sa.String(length=100), nullable=True), schema=SCHEMA)
    op.add_column("oferentes", sa.Column("experiencia", sa.String(length=20), nullable=True), schema=SCHEMA)
    op.add_column("oferentes", sa.Column("info_guardia", sa.String(length=200), nullable=True), schema=SCHEMA)

    # --- OFERENTE_DIAS_ATENCION ---------------------------------------------
    op.create_table(
        "oferente_dias_atencion",
        sa.Column("oferente_id", sa.Integer(), nullable=False),
        sa.Column("dia", sa.SmallInteger(), nullable=False),
        sa.CheckConstraint("dia BETWEEN 1 AND 7", name="ck_dia_atencion_rango"),
        sa.ForeignKeyConstraint(["oferente_id"], [f"{SCHEMA}.oferentes.id_oferente"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("oferente_id", "dia"),
        schema=SCHEMA,
    )

    # --- TRABAJOS_REALIZADOS ------------------------------------------------
    op.create_table(
        "trabajos_realizados",
        sa.Column("id_trabajo", sa.Integer(), nullable=False),
        sa.Column("oferente_id", sa.Integer(), nullable=False),
        sa.Column("titulo", sa.String(length=100), nullable=True),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("fecha_creacion", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["oferente_id"], [f"{SCHEMA}.oferentes.id_oferente"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id_trabajo"),
        schema=SCHEMA,
    )
    op.create_index("ix_offix_trabajos_realizados_id_trabajo", "trabajos_realizados", ["id_trabajo"], schema=SCHEMA)
    op.create_index("ix_offix_trabajos_realizados_oferente_id", "trabajos_realizados", ["oferente_id"], schema=SCHEMA)

    # --- ARCHIVOS_ADJUNTOS --------------------------------------------------
    op.alter_column("archivos_adjuntos", "url_archivo", new_column_name="storage_path", schema=SCHEMA)
    op.add_column(
        "archivos_adjuntos",
        sa.Column("content_type", sa.String(length=50), nullable=False, server_default="image/jpeg"),
        schema=SCHEMA,
    )
    op.add_column(
        "archivos_adjuntos",
        sa.Column("tamano_bytes", sa.Integer(), nullable=False, server_default="0"),
        schema=SCHEMA,
    )
    op.alter_column("archivos_adjuntos", "content_type", server_default=None, schema=SCHEMA)
    op.alter_column("archivos_adjuntos", "tamano_bytes", server_default=None, schema=SCHEMA)
    op.add_column("archivos_adjuntos", sa.Column("trabajo_id", sa.Integer(), nullable=True), schema=SCHEMA)
    op.add_column("archivos_adjuntos", sa.Column("orden", sa.SmallInteger(), nullable=True), schema=SCHEMA)
    op.create_foreign_key(
        "fk_archivos_trabajo",
        "archivos_adjuntos",
        "trabajos_realizados",
        ["trabajo_id"],
        ["id_trabajo"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="CASCADE",
    )
    op.create_index("ix_offix_archivos_adjuntos_trabajo_id", "archivos_adjuntos", ["trabajo_id"], schema=SCHEMA)
    op.create_unique_constraint("uq_archivo_trabajo_orden", "archivos_adjuntos", ["trabajo_id", "orden"], schema=SCHEMA)
    op.create_check_constraint(
        "ck_archivo_orden_rango",
        "archivos_adjuntos",
        "orden IS NULL OR orden BETWEEN 1 AND 5",
        schema=SCHEMA,
    )
    op.create_unique_constraint("uq_archivos_adjuntos_storage_path", "archivos_adjuntos", ["storage_path"], schema=SCHEMA)

    # --- RESENAS y SOLICITUDES_RESENA ---------------------------------------
    op.create_unique_constraint("uq_resena_solicitud", "resenas", ["solicitud_id"], schema=SCHEMA)
    op.create_index(
        "idx_solicitud_email_fecha",
        "solicitudes_resena",
        ["email_cliente", "fecha_generacion"],
        schema=SCHEMA,
    )

    # --- Normalización de las filas existentes ------------------------------
    op.execute(NORMALIZAR_DNI)
    op.execute(NORMALIZAR_TELEFONO)
    op.execute(HORARIOS_POR_DEFECTO)
    op.execute(DIAS_LABORABLES_POR_DEFECTO)


def downgrade() -> None:
    op.drop_index("idx_solicitud_email_fecha", table_name="solicitudes_resena", schema=SCHEMA)
    op.drop_constraint("uq_resena_solicitud", "resenas", schema=SCHEMA, type_="unique")

    op.drop_constraint("uq_archivos_adjuntos_storage_path", "archivos_adjuntos", schema=SCHEMA, type_="unique")
    op.drop_constraint("ck_archivo_orden_rango", "archivos_adjuntos", schema=SCHEMA, type_="check")
    op.drop_constraint("uq_archivo_trabajo_orden", "archivos_adjuntos", schema=SCHEMA, type_="unique")
    op.drop_index("ix_offix_archivos_adjuntos_trabajo_id", table_name="archivos_adjuntos", schema=SCHEMA)
    op.drop_constraint("fk_archivos_trabajo", "archivos_adjuntos", schema=SCHEMA, type_="foreignkey")
    op.drop_column("archivos_adjuntos", "orden", schema=SCHEMA)
    op.drop_column("archivos_adjuntos", "trabajo_id", schema=SCHEMA)
    op.drop_column("archivos_adjuntos", "tamano_bytes", schema=SCHEMA)
    op.drop_column("archivos_adjuntos", "content_type", schema=SCHEMA)
    op.alter_column("archivos_adjuntos", "storage_path", new_column_name="url_archivo", schema=SCHEMA)

    op.drop_index("ix_offix_trabajos_realizados_oferente_id", table_name="trabajos_realizados", schema=SCHEMA)
    op.drop_index("ix_offix_trabajos_realizados_id_trabajo", table_name="trabajos_realizados", schema=SCHEMA)
    op.drop_table("trabajos_realizados", schema=SCHEMA)

    op.drop_table("oferente_dias_atencion", schema=SCHEMA)

    op.drop_column("oferentes", "info_guardia", schema=SCHEMA)
    op.drop_column("oferentes", "experiencia", schema=SCHEMA)
    op.drop_column("oferentes", "especialidad", schema=SCHEMA)

    # Se reconstruye apellido desde el nombre completo: lo que sigue al primer espacio.
    op.add_column("oferentes", sa.Column("apellido", sa.String(length=100), nullable=True), schema=SCHEMA)
    op.execute(
        "UPDATE offix.oferentes SET apellido = CASE WHEN position(' ' in nombre) > 0 "
        "THEN substr(nombre, position(' ' in nombre) + 1) ELSE '' END, "
        "nombre = split_part(nombre, ' ', 1)"
    )
    op.alter_column("oferentes", "apellido", nullable=False, schema=SCHEMA)
    op.alter_column("oferentes", "nombre", type_=sa.String(length=100), schema=SCHEMA)

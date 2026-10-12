"""Límites anti-spam sobre emisiones de enlace y título obligatorio en trabajos

Revision ID: c4f1a8e2b9d7
Revises: 5e1c2a9b7d30
Create Date: 2026-10-12 10:00:00

Cambios (ver docs/plan-sprint-2.md, "Revisión 3"):

- EMISIONES_RESENA (nueva): una fila por cada enlace de reseña que sale, el
  nuevo y también cada reenvío. Los límites de 24 h cuentan esta tabla. Antes
  contaban SOLICITUDES_RESENA, y reenviar un enlace existente no sumaba cupo.
  Se carga con las solicitudes de las últimas 24 h, así los límites siguen
  igual en el momento de migrar.
- TRABAJOS_REALIZADOS.titulo pasa a NOT NULL: el título es obligatorio.

Solo se ejecuta en PostgreSQL (env.py rechaza SQLite).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4f1a8e2b9d7"
down_revision: Union[str, None] = "5e1c2a9b7d30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "offix"

# Los trabajos cargados antes de esta migración pueden no tener título. La tabla
# es de Sprint 2 y todavía no tiene datos reales; el texto es solo para que la
# restricción pueda aplicarse.
TITULO_FALTANTE = "UPDATE offix.trabajos_realizados SET titulo = 'Sin título' WHERE titulo IS NULL"

COPIAR_EMISIONES_24_HORAS = """
INSERT INTO offix.emisiones_resena (solicitud_id, oferente_id, email_cliente, fecha_emision)
SELECT id_solicitud, oferente_id, email_cliente, fecha_generacion
FROM offix.solicitudes_resena
WHERE fecha_generacion >= now() - interval '24 hours'
"""


def upgrade() -> None:
    # --- EMISIONES_RESENA ---------------------------------------------------
    op.create_table(
        "emisiones_resena",
        sa.Column("id_emision", sa.Integer(), nullable=False),
        sa.Column("solicitud_id", sa.Integer(), nullable=False),
        sa.Column("oferente_id", sa.Integer(), nullable=False),
        sa.Column("email_cliente", sa.String(length=255), nullable=True),
        sa.Column("fecha_emision", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["solicitud_id"], [f"{SCHEMA}.solicitudes_resena.id_solicitud"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["oferente_id"], [f"{SCHEMA}.oferentes.id_oferente"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id_emision"),
        schema=SCHEMA,
    )
    op.create_index("ix_offix_emisiones_resena_id_emision", "emisiones_resena", ["id_emision"], schema=SCHEMA)
    op.create_index("ix_offix_emisiones_resena_solicitud_id", "emisiones_resena", ["solicitud_id"], schema=SCHEMA)
    op.create_index(
        "idx_emision_email_fecha", "emisiones_resena", ["email_cliente", "fecha_emision"], schema=SCHEMA
    )
    op.create_index(
        "idx_emision_oferente_fecha", "emisiones_resena", ["oferente_id", "fecha_emision"], schema=SCHEMA
    )
    op.execute(COPIAR_EMISIONES_24_HORAS)

    # El índice de solicitudes ya no lo usa ningún límite.
    op.drop_index("idx_solicitud_email_fecha", table_name="solicitudes_resena", schema=SCHEMA)

    # --- TRABAJOS_REALIZADOS ------------------------------------------------
    op.execute(TITULO_FALTANTE)
    op.alter_column("trabajos_realizados", "titulo", existing_type=sa.String(length=100), nullable=False, schema=SCHEMA)


def downgrade() -> None:
    op.alter_column("trabajos_realizados", "titulo", existing_type=sa.String(length=100), nullable=True, schema=SCHEMA)

    op.create_index(
        "idx_solicitud_email_fecha",
        "solicitudes_resena",
        ["email_cliente", "fecha_generacion"],
        schema=SCHEMA,
    )

    op.drop_index("idx_emision_oferente_fecha", table_name="emisiones_resena", schema=SCHEMA)
    op.drop_index("idx_emision_email_fecha", table_name="emisiones_resena", schema=SCHEMA)
    op.drop_index("ix_offix_emisiones_resena_solicitud_id", table_name="emisiones_resena", schema=SCHEMA)
    op.drop_index("ix_offix_emisiones_resena_id_emision", table_name="emisiones_resena", schema=SCHEMA)
    op.drop_table("emisiones_resena", schema=SCHEMA)

"""agregar fidelizado a usuarios (HU-02, CA08)

Revision ID: a3f1c9d27b54
Revises: 5e1c2a9b7d30
Create Date: 2026-10-11 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f1c9d27b54'
down_revision: Union[str, None] = '5e1c2a9b7d30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'usuarios',
        sa.Column('fidelizado', sa.Boolean(), server_default=sa.false(), nullable=False),
        schema='offix',
    )
    # Los que ya tenían una matrícula fidelizada antes de que existiera la columna.
    op.execute(
        "UPDATE offix.usuarios SET fidelizado = true "
        "WHERE id_usuario IN (SELECT oferente_id FROM offix.matriculas)"
    )


def downgrade() -> None:
    op.drop_column('usuarios', 'fidelizado', schema='offix')

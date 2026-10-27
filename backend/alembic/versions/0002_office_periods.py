"""Períodos de exercício dos parlamentares (suplências, licenças, vacâncias).

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-27 14:50:50.278124
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("politicians", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "office_periods",
                sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
                nullable=True,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("politicians", schema=None) as batch_op:
        batch_op.drop_column("office_periods")

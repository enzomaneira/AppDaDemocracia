"""Fidelidade ao partido e alinhamento com o governo.

Guarda a orientação do líder do governo em cada votação e as duas taxas em politician_stats.

Revision ID: 0007
Revises: 0006
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("votes", schema=None) as batch_op:
        batch_op.add_column(sa.Column("government_orientation", sa.String(20), nullable=True))
    with op.batch_alter_table("politician_stats", schema=None) as batch_op:
        batch_op.add_column(sa.Column("party_alignment_rate", sa.Numeric(5, 2), nullable=True))
        batch_op.add_column(
            sa.Column("party_votes_compared", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(sa.Column("government_alignment_rate", sa.Numeric(5, 2), nullable=True))
        batch_op.add_column(
            sa.Column("government_votes_compared", sa.Integer(), nullable=False, server_default="0")
        )


def downgrade() -> None:
    with op.batch_alter_table("politician_stats", schema=None) as batch_op:
        batch_op.drop_column("government_votes_compared")
        batch_op.drop_column("government_alignment_rate")
        batch_op.drop_column("party_votes_compared")
        batch_op.drop_column("party_alignment_rate")
    with op.batch_alter_table("votes", schema=None) as batch_op:
        batch_op.drop_column("government_orientation")

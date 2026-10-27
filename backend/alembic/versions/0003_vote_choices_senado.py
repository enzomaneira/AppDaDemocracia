"""Novos estados de voto do Senado: secreto, presente sem voto e ausência justificada.

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_VALUES = ("secreto", "presente", "justificada")


ALL_VALUES = ("sim", "nao", "abstencao", "obstrucao", "ausente", "art17", *NEW_VALUES)


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        # SQLite: o enum é um VARCHAR do tamanho do maior valor; "justificada" não cabia.
        with op.batch_alter_table("vote_records") as batch:
            batch.alter_column(
                "choice",
                existing_type=sa.String(9),
                type_=sa.Enum(*ALL_VALUES, name="vote_choice"),
                existing_nullable=False,
            )
        return
    # ADD VALUE não pode rodar no mesmo bloco de transação em que o valor é usado.
    with op.get_context().autocommit_block():
        for value in NEW_VALUES:
            op.execute(f"ALTER TYPE vote_choice ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    # O Postgres não remove valores de um enum; os registros com esses estados voltam a
    # "ausente" para manter o esquema compatível com a versão anterior.
    if op.get_bind().dialect.name != "postgresql":
        return
    values = ", ".join(f"'{v}'" for v in NEW_VALUES)
    op.execute(f"UPDATE vote_records SET choice = 'ausente' WHERE choice::text IN ({values})")

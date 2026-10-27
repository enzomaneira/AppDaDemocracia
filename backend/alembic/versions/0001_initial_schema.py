"""Esquema inicial: usuários, dados políticos, notícias, feed e operação.

Revision ID: 0001
Revises:
Create Date: 2026-10-27 13:53:19.163886
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enum(*values: str, name: str) -> sa.Enum:
    """Enum portável: no Postgres o tipo é criado uma vez antes das tabelas."""
    return sa.Enum(*values, name=name).with_variant(
        postgresql.ENUM(*values, name=name, create_type=False), "postgresql"
    )


ENUMS = {
    "house": _enum("camara", "senado", name="house"),
    "attendance_status": _enum("presente", "ausente", "justificada", name="attendance_status"),
    "author_role": _enum("autor", "relator", name="author_role"),
    "feed_type": _enum("vote", "agenda", "news", "bill", name="feed_type"),
    "vote_choice": _enum(
        "sim", "nao", "abstencao", "obstrucao", "ausente", "art17", name="vote_choice"
    ),
}


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"
    if is_pg:
        op.execute("CREATE EXTENSION IF NOT EXISTS citext")
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        for e in ENUMS.values():
            postgresql.ENUM(*e.enums, name=e.name).create(bind, checkfirst=True)

    op.create_table(
        "bills",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("house", ENUMS["house"], nullable=False),
        sa.Column("external_id", sa.String(length=40), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("number", sa.Integer(), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("official_summary", sa.Text(), nullable=True),
        sa.Column("plain_summary", sa.Text(), nullable=True),
        sa.Column("plain_summary_ai", sa.Boolean(), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bills")),
        sa.UniqueConstraint("house", "external_id", name="uq_bills_house_ext"),
    )
    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("job", sa.String(length=60), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("items_upserted", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ingestion_runs")),
    )
    with op.batch_alter_table("ingestion_runs", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_ingestion_runs_job"), ["job"], unique=False)

    op.create_table(
        "news_articles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("url", sa.String(length=1000), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("source_name", sa.String(length=200), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("image_url", sa.String(length=1000), nullable=True),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_news_articles")),
        sa.UniqueConstraint("url", name=op.f("uq_news_articles_url")),
    )
    with op.batch_alter_table("news_articles", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_news_articles_published_at"), ["published_at"], unique=False
        )

    op.create_table(
        "parties",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("acronym", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=True),
        sa.Column("external_id", sa.String(length=40), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_parties")),
        sa.UniqueConstraint("acronym", name=op.f("uq_parties_acronym")),
    )
    op.create_table(
        "sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("house", ENUMS["house"], nullable=False),
        sa.Column("external_id", sa.String(length=40), nullable=False),
        sa.Column("type", sa.String(length=120), nullable=True),
        sa.Column("is_deliberative", sa.Boolean(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessions")),
        sa.UniqueConstraint("house", "external_id", name="uq_sessions_house_ext"),
    )
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_sessions_starts_at"), ["starts_at"], unique=False)

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "email",
            sa.String(length=320).with_variant(postgresql.CITEXT(), "postgresql"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("auth_provider", sa.String(length=20), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("uf", sa.String(length=2), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_table(
        "politicians",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("house", ENUMS["house"], nullable=False),
        sa.Column("external_id", sa.String(length=40), nullable=False),
        sa.Column("civil_name", sa.String(length=200), nullable=False),
        sa.Column("parliamentary_name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=220), nullable=False),
        sa.Column("party_id", sa.Uuid(), nullable=True),
        sa.Column("uf", sa.String(length=2), nullable=False),
        sa.Column("photo_url", sa.String(length=500), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column(
            "social_links",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("in_office", sa.Boolean(), nullable=False),
        sa.Column("legislature", sa.Integer(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["party_id"], ["parties.id"], name=op.f("fk_politicians_party_id_parties")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_politicians")),
        sa.UniqueConstraint("house", "external_id", name="uq_politicians_house_ext"),
        sa.UniqueConstraint("slug", name=op.f("uq_politicians_slug")),
    )
    with op.batch_alter_table("politicians", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_politicians_parliamentary_name"), ["parliamentary_name"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_politicians_uf"), ["uf"], unique=False)

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_refresh_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_refresh_tokens_token_hash")),
    )
    with op.batch_alter_table("refresh_tokens", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_refresh_tokens_user_id"), ["user_id"], unique=False)

    op.create_table(
        "votes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("house", ENUMS["house"], nullable=False),
        sa.Column("external_id", sa.String(length=40), nullable=False),
        sa.Column("bill_id", sa.Uuid(), nullable=True),
        sa.Column("voted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("result", sa.String(length=200), nullable=True),
        sa.Column("yes_count", sa.Integer(), nullable=False),
        sa.Column("no_count", sa.Integer(), nullable=False),
        sa.Column("abstention_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["bill_id"], ["bills.id"], name=op.f("fk_votes_bill_id_bills")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_votes")),
        sa.UniqueConstraint("house", "external_id", name="uq_votes_house_ext"),
    )
    with op.batch_alter_table("votes", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_votes_voted_at"), ["voted_at"], unique=False)

    op.create_table(
        "agenda_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("house", ENUMS["house"], nullable=False),
        sa.Column("external_id", sa.String(length=40), nullable=False),
        sa.Column("politician_id", sa.Uuid(), nullable=True),
        sa.Column("organ", sa.String(length=200), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("location", sa.String(length=300), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=60), nullable=True),
        sa.ForeignKeyConstraint(
            ["politician_id"],
            ["politicians.id"],
            name=op.f("fk_agenda_events_politician_id_politicians"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agenda_events")),
        sa.UniqueConstraint(
            "house", "external_id", "politician_id", name="uq_agenda_house_ext_pol"
        ),
    )
    with op.batch_alter_table("agenda_events", schema=None) as batch_op:
        batch_op.create_index(
            "ix_agenda_politician_starts", ["politician_id", "starts_at"], unique=False
        )

    op.create_table(
        "attendance",
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("politician_id", sa.Uuid(), nullable=False),
        sa.Column("status", ENUMS["attendance_status"], nullable=False),
        sa.Column("justification", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["politician_id"],
            ["politicians.id"],
            name=op.f("fk_attendance_politician_id_politicians"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.id"],
            name=op.f("fk_attendance_session_id_sessions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("session_id", "politician_id", name=op.f("pk_attendance")),
    )
    with op.batch_alter_table("attendance", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_attendance_politician_id"), ["politician_id"], unique=False
        )

    op.create_table(
        "bill_authors",
        sa.Column("bill_id", sa.Uuid(), nullable=False),
        sa.Column("politician_id", sa.Uuid(), nullable=False),
        sa.Column("role", ENUMS["author_role"], nullable=False),
        sa.ForeignKeyConstraint(
            ["bill_id"],
            ["bills.id"],
            name=op.f("fk_bill_authors_bill_id_bills"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["politician_id"],
            ["politicians.id"],
            name=op.f("fk_bill_authors_politician_id_politicians"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("bill_id", "politician_id", "role", name=op.f("pk_bill_authors")),
    )
    with op.batch_alter_table("bill_authors", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_bill_authors_politician_id"), ["politician_id"], unique=False
        )

    op.create_table(
        "expenses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("politician_id", sa.Uuid(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=200), nullable=False),
        sa.Column("supplier", sa.String(length=300), nullable=True),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("document_url", sa.String(length=500), nullable=True),
        sa.Column("external_id", sa.String(length=80), nullable=False),
        sa.ForeignKeyConstraint(
            ["politician_id"],
            ["politicians.id"],
            name=op.f("fk_expenses_politician_id_politicians"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_expenses")),
        sa.UniqueConstraint("external_id", name=op.f("uq_expenses_external_id")),
    )
    with op.batch_alter_table("expenses", schema=None) as batch_op:
        batch_op.create_index(
            "ix_expenses_politician_year", ["politician_id", "year"], unique=False
        )

    op.create_table(
        "feed_events",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("politician_id", sa.Uuid(), nullable=False),
        sa.Column("type", ENUMS["feed_type"], nullable=False),
        sa.Column("ref_id", sa.Uuid(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "payload",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["politician_id"],
            ["politicians.id"],
            name=op.f("fk_feed_events_politician_id_politicians"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_feed_events")),
    )
    with op.batch_alter_table("feed_events", schema=None) as batch_op:
        batch_op.create_index(
            "ix_feed_politician_occurred", ["politician_id", "occurred_at"], unique=False
        )

    op.create_table(
        "follows",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("politician_id", sa.Uuid(), nullable=False),
        sa.Column("notify_votes", sa.Boolean(), nullable=False),
        sa.Column("notify_agenda", sa.Boolean(), nullable=False),
        sa.Column("notify_news", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["politician_id"],
            ["politicians.id"],
            name=op.f("fk_follows_politician_id_politicians"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_follows_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "politician_id", name=op.f("pk_follows")),
    )
    op.create_table(
        "news_mentions",
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("politician_id", sa.Uuid(), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=3, scale=2), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["article_id"],
            ["news_articles.id"],
            name=op.f("fk_news_mentions_article_id_news_articles"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["politician_id"],
            ["politicians.id"],
            name=op.f("fk_news_mentions_politician_id_politicians"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("article_id", "politician_id", name=op.f("pk_news_mentions")),
    )
    with op.batch_alter_table("news_mentions", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_news_mentions_politician_id"), ["politician_id"], unique=False
        )

    op.create_table(
        "politician_stats",
        sa.Column("politician_id", sa.Uuid(), nullable=False),
        sa.Column("period", sa.String(length=20), nullable=False),
        sa.Column("sessions_total", sa.Integer(), nullable=False),
        sa.Column("sessions_present", sa.Integer(), nullable=False),
        sa.Column("sessions_justified", sa.Integer(), nullable=False),
        sa.Column("attendance_rate", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("votes_participated", sa.Integer(), nullable=False),
        sa.Column("votes_total", sa.Integer(), nullable=False),
        sa.Column("bills_authored", sa.Integer(), nullable=False),
        sa.Column("bills_reported", sa.Integer(), nullable=False),
        sa.Column("expenses_total", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column(
            "house_avg",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["politician_id"],
            ["politicians.id"],
            name=op.f("fk_politician_stats_politician_id_politicians"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("politician_id", "period", name=op.f("pk_politician_stats")),
    )
    op.create_table(
        "vote_records",
        sa.Column("vote_id", sa.Uuid(), nullable=False),
        sa.Column("politician_id", sa.Uuid(), nullable=False),
        sa.Column("choice", ENUMS["vote_choice"], nullable=False),
        sa.Column("party_orientation", sa.String(length=20), nullable=True),
        sa.ForeignKeyConstraint(
            ["politician_id"],
            ["politicians.id"],
            name=op.f("fk_vote_records_politician_id_politicians"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["vote_id"],
            ["votes.id"],
            name=op.f("fk_vote_records_vote_id_votes"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("vote_id", "politician_id", name=op.f("pk_vote_records")),
    )
    with op.batch_alter_table("vote_records", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_vote_records_politician_id"), ["politician_id"], unique=False
        )

    if is_pg:
        op.execute(
            "CREATE INDEX ix_politicians_name_trgm ON politicians "
            "USING gin (parliamentary_name gin_trgm_ops)"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_politicians_name_trgm")
    with op.batch_alter_table("vote_records", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_vote_records_politician_id"))

    op.drop_table("vote_records")
    op.drop_table("politician_stats")
    with op.batch_alter_table("news_mentions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_news_mentions_politician_id"))

    op.drop_table("news_mentions")
    op.drop_table("follows")
    with op.batch_alter_table("feed_events", schema=None) as batch_op:
        batch_op.drop_index("ix_feed_politician_occurred")

    op.drop_table("feed_events")
    with op.batch_alter_table("expenses", schema=None) as batch_op:
        batch_op.drop_index("ix_expenses_politician_year")

    op.drop_table("expenses")
    with op.batch_alter_table("bill_authors", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_bill_authors_politician_id"))

    op.drop_table("bill_authors")
    with op.batch_alter_table("attendance", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_attendance_politician_id"))

    op.drop_table("attendance")
    with op.batch_alter_table("agenda_events", schema=None) as batch_op:
        batch_op.drop_index("ix_agenda_politician_starts")

    op.drop_table("agenda_events")
    with op.batch_alter_table("votes", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_votes_voted_at"))

    op.drop_table("votes")
    with op.batch_alter_table("refresh_tokens", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_refresh_tokens_user_id"))

    op.drop_table("refresh_tokens")
    with op.batch_alter_table("politicians", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_politicians_uf"))
        batch_op.drop_index(batch_op.f("ix_politicians_parliamentary_name"))

    op.drop_table("politicians")
    op.drop_table("users")
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_sessions_starts_at"))

    op.drop_table("sessions")
    op.drop_table("parties")
    with op.batch_alter_table("news_articles", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_news_articles_published_at"))

    op.drop_table("news_articles")
    with op.batch_alter_table("ingestion_runs", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_ingestion_runs_job"))

    op.drop_table("ingestion_runs")
    op.drop_table("bills")
    if bind.dialect.name == "postgresql":
        for e in ENUMS.values():
            postgresql.ENUM(*e.enums, name=e.name).drop(bind, checkfirst=True)

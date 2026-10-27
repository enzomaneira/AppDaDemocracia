from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, MetaData, String, TypeDecorator
from sqlalchemy.dialects.postgresql import CITEXT, JSONB
from sqlalchemy.orm import DeclarativeBase

# Tipos portáveis: no PostgreSQL usam citext/jsonb; no SQLite (dev/testes) caem para String/JSON.
JsonType = JSON().with_variant(JSONB(), "postgresql")
EmailType = String(320).with_variant(CITEXT(), "postgresql")


class UTCDateTime(TypeDecorator):
    """DateTime sempre em UTC e com fuso (o SQLite devolve datetimes sem fuso)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect):
        if value is not None and value.tzinfo is not None:
            value = value.astimezone(UTC)
            if dialect.name == "sqlite":
                value = value.replace(tzinfo=None)
        return value

    def process_result_value(self, value: datetime | None, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value


convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=convention)

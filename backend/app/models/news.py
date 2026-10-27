import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, JsonType, UTCDateTime

# SQLite só autoincrementa INTEGER PRIMARY KEY; no Postgres vira bigserial.
BigIntPK = BigInteger().with_variant(Integer(), "sqlite")


class FeedType(enum.StrEnum):
    vote = "vote"
    agenda = "agenda"
    news = "news"
    bill = "bill"


class NewsArticle(Base):
    """Guarda só título, trecho curto, fonte e link — nunca a matéria inteira."""

    __tablename__ = "news_articles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    url: Mapped[str] = mapped_column(String(1000), unique=True)
    title: Mapped[str] = mapped_column(Text)
    snippet: Mapped[str | None] = mapped_column(Text)
    source_name: Mapped[str | None] = mapped_column(String(200))
    published_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    image_url: Mapped[str | None] = mapped_column(String(1000))
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now())


class NewsMention(Base):
    __tablename__ = "news_mentions"

    article_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("news_articles.id", ondelete="CASCADE"), primary_key=True
    )
    politician_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("politicians.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    confidence: Mapped[float] = mapped_column(Numeric(3, 2))
    verified: Mapped[bool] = mapped_column(Boolean, default=False)


class FeedEvent(Base):
    __tablename__ = "feed_events"
    __table_args__ = (Index("ix_feed_politician_occurred", "politician_id", "occurred_at"),)

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    politician_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("politicians.id", ondelete="CASCADE")
    )
    type: Mapped[FeedType] = mapped_column(
        Enum(FeedType, name="feed_type", values_callable=lambda x: [m.value for m in x])
    )
    ref_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime)
    payload: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(40))
    job: Mapped[str] = mapped_column(String(60), index=True)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    status: Mapped[str] = mapped_column(String(20), default="running")  # running|ok|error
    items_upserted: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)

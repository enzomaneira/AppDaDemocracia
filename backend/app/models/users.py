import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, EmailType, UTCDateTime


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(EmailType, unique=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    auth_provider: Mapped[str] = mapped_column(String(20), default="email")  # email | google
    role: Mapped[str] = mapped_column(String(20), default="user")  # user | admin
    uf: Mapped[str | None] = mapped_column(String(2))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class Follow(Base):
    """Lista de seguidos: dado sensível (RNF05), nunca exposto publicamente."""

    __tablename__ = "follows"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    politician_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("politicians.id", ondelete="CASCADE"), primary_key=True
    )
    notify_votes: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_agenda: Mapped[bool] = mapped_column(Boolean, default=False)
    notify_news: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now())


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

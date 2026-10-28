import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, EmailType, JsonType, UTCDateTime


class WaitlistEntry(Base):
    """Inscrição na lista de espera + respostas da pesquisa (LGPD: só o necessário)."""

    __tablename__ = "waitlist_entries"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(EmailType, unique=True)
    name: Mapped[str | None] = mapped_column(String(120))
    uf: Mapped[str | None] = mapped_column(String(2))
    age_range: Mapped[str | None] = mapped_column(String(10))
    answers: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    survey_version: Mapped[int] = mapped_column(Integer, default=1)
    # De onde a pessoa veio (ex.: "instagram", "?ref=..."), para saber o que funciona.
    source: Mapped[str | None] = mapped_column(String(60))
    consent_at: Mapped[datetime] = mapped_column(UTCDateTime)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, server_default=func.now(), onupdate=func.now()
    )

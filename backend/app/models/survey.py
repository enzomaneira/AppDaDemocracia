import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, JsonType, UTCDateTime


class SurveyResponse(Base):
    """Respostas da pesquisa de cada conta. Opcional: nunca é condição para usar o app.

    Também guarda se a pessoa dispensou ("Agora não") e se já viu o lembrete, para que o
    convite apareça no máximo duas vezes.
    """

    __tablename__ = "survey_responses"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    answers: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    survey_version: Mapped[int] = mapped_column(Integer, default=1)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    dismissed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    reminded_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, server_default=func.now(), onupdate=func.now()
    )

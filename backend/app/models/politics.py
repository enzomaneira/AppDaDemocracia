import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JsonType, UTCDateTime


class House(enum.StrEnum):
    camara = "camara"
    senado = "senado"


class AttendanceStatus(enum.StrEnum):
    presente = "presente"
    ausente = "ausente"
    justificada = "justificada"


class AuthorRole(enum.StrEnum):
    autor = "autor"
    relator = "relator"


class VoteChoice(enum.StrEnum):
    sim = "sim"
    nao = "nao"
    abstencao = "abstencao"
    obstrucao = "obstrucao"
    ausente = "ausente"
    art17 = "art17"  # presidindo a sessão (Câmara: art. 17; Senado: art. 51)
    # Senado: o registro nominal traz o comparecimento de cada senador.
    secreto = "secreto"  # votou em escrutínio secreto
    presente = "presente"  # presente, não registrou voto
    justificada = "justificada"  # atividade parlamentar, missão oficial ou licença


# Escolhas que contam como "participou da votação".
PARTICIPATED_CHOICES = (
    VoteChoice.sim,
    VoteChoice.nao,
    VoteChoice.abstencao,
    VoteChoice.obstrucao,
    VoteChoice.secreto,
    VoteChoice.art17,
)


def _enum(e: type[enum.Enum], name: str) -> Enum:
    return Enum(e, name=name, values_callable=lambda x: [m.value for m in x])


HouseEnum = _enum(House, "house")


class Party(Base):
    __tablename__ = "parties"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    acronym: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str | None] = mapped_column(String(200))
    external_id: Mapped[str | None] = mapped_column(String(40))


class Politician(Base):
    __tablename__ = "politicians"
    __table_args__ = (UniqueConstraint("house", "external_id", name="uq_politicians_house_ext"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    house: Mapped[House] = mapped_column(HouseEnum)
    external_id: Mapped[str] = mapped_column(String(40))
    civil_name: Mapped[str] = mapped_column(String(200))
    parliamentary_name: Mapped[str] = mapped_column(String(200), index=True)
    slug: Mapped[str] = mapped_column(String(220), unique=True)
    party_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("parties.id"))
    uf: Mapped[str] = mapped_column(String(2), index=True)
    photo_url: Mapped[str | None] = mapped_column(String(500))
    email: Mapped[str | None] = mapped_column(String(320))
    social_links: Mapped[list[str]] = mapped_column(JsonType, default=list)
    in_office: Mapped[bool] = mapped_column(Boolean, default=True)
    # Períodos em exercício [[início, fim|None], ...] (datas ISO), do histórico oficial.
    office_periods: Mapped[list | None] = mapped_column(JsonType)
    legislature: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, server_default=func.now(), onupdate=func.now()
    )

    party: Mapped[Party | None] = relationship(lazy="joined")


class Session(Base):
    """Sessão do Plenário; só as deliberativas entram no cálculo de presença."""

    __tablename__ = "sessions"
    __table_args__ = (UniqueConstraint("house", "external_id", name="uq_sessions_house_ext"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    house: Mapped[House] = mapped_column(HouseEnum)
    external_id: Mapped[str] = mapped_column(String(40))
    type: Mapped[str | None] = mapped_column(String(120))
    is_deliberative: Mapped[bool] = mapped_column(Boolean, default=False)
    starts_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    title: Mapped[str | None] = mapped_column(Text)


class Attendance(Base):
    __tablename__ = "attendance"

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), primary_key=True
    )
    politician_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("politicians.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    status: Mapped[AttendanceStatus] = mapped_column(_enum(AttendanceStatus, "attendance_status"))
    justification: Mapped[str | None] = mapped_column(Text)


class AgendaEvent(Base):
    __tablename__ = "agenda_events"
    __table_args__ = (
        UniqueConstraint("house", "external_id", "politician_id", name="uq_agenda_house_ext_pol"),
        Index("ix_agenda_politician_starts", "politician_id", "starts_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    house: Mapped[House] = mapped_column(HouseEnum)
    external_id: Mapped[str] = mapped_column(String(40))
    politician_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("politicians.id", ondelete="CASCADE")
    )
    organ: Mapped[str | None] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(300))
    starts_at: Mapped[datetime] = mapped_column(UTCDateTime)
    ends_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    status: Mapped[str | None] = mapped_column(String(60))


class Bill(Base):
    __tablename__ = "bills"
    __table_args__ = (UniqueConstraint("house", "external_id", name="uq_bills_house_ext"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    house: Mapped[House] = mapped_column(HouseEnum)
    external_id: Mapped[str] = mapped_column(String(40))
    type: Mapped[str] = mapped_column(String(20))
    number: Mapped[int | None] = mapped_column(Integer)
    year: Mapped[int | None] = mapped_column(Integer)
    official_summary: Mapped[str | None] = mapped_column(Text)
    plain_summary: Mapped[str | None] = mapped_column(Text)
    plain_summary_ai: Mapped[bool] = mapped_column(Boolean, default=False)
    url: Mapped[str | None] = mapped_column(String(500))


class BillAuthor(Base):
    __tablename__ = "bill_authors"

    bill_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bills.id", ondelete="CASCADE"), primary_key=True
    )
    politician_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("politicians.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    role: Mapped[AuthorRole] = mapped_column(_enum(AuthorRole, "author_role"), primary_key=True)


class Vote(Base):
    __tablename__ = "votes"
    __table_args__ = (UniqueConstraint("house", "external_id", name="uq_votes_house_ext"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    house: Mapped[House] = mapped_column(HouseEnum)
    external_id: Mapped[str] = mapped_column(String(40))
    bill_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("bills.id"))
    voted_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    result: Mapped[str | None] = mapped_column(String(200))
    yes_count: Mapped[int] = mapped_column(Integer, default=0)
    no_count: Mapped[int] = mapped_column(Integer, default=0)
    abstention_count: Mapped[int] = mapped_column(Integer, default=0)

    bill: Mapped[Bill | None] = relationship(lazy="joined")


class VoteRecord(Base):
    __tablename__ = "vote_records"

    vote_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("votes.id", ondelete="CASCADE"), primary_key=True
    )
    politician_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("politicians.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    choice: Mapped[VoteChoice] = mapped_column(_enum(VoteChoice, "vote_choice"))
    party_orientation: Mapped[str | None] = mapped_column(String(20))


class Expense(Base):
    __tablename__ = "expenses"
    __table_args__ = (Index("ix_expenses_politician_year", "politician_id", "year"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    politician_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("politicians.id", ondelete="CASCADE")
    )
    year: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(String(200))
    supplier: Mapped[str | None] = mapped_column(String(300))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    document_url: Mapped[str | None] = mapped_column(String(500))
    # Chave da fonte para upsert idempotente (código do documento ou hash da linha).
    external_id: Mapped[str] = mapped_column(String(80), unique=True)


class PoliticianStats(Base):
    """Estatísticas pré-calculadas por refresh_stats (equivale à visão materializada do projeto)."""

    __tablename__ = "politician_stats"

    politician_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("politicians.id", ondelete="CASCADE"), primary_key=True
    )
    period: Mapped[str] = mapped_column(String(20), primary_key=True)  # "leg57" ou "2026"
    sessions_total: Mapped[int] = mapped_column(Integer, default=0)
    sessions_present: Mapped[int] = mapped_column(Integer, default=0)
    sessions_justified: Mapped[int] = mapped_column(Integer, default=0)
    attendance_rate: Mapped[float | None] = mapped_column(Numeric(5, 2))
    votes_participated: Mapped[int] = mapped_column(Integer, default=0)
    votes_total: Mapped[int] = mapped_column(Integer, default=0)
    bills_authored: Mapped[int] = mapped_column(Integer, default=0)
    bills_reported: Mapped[int] = mapped_column(Integer, default=0)
    expenses_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    house_avg: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    computed_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now())

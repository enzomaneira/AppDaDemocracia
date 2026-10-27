"""Schemas Pydantic expostos pela API (OpenAPI em /docs)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field

T = TypeVar("T")


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: str | None = None


# --- Auth -----------------------------------------------------------------


class RegisterIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=128)
    uf: str | None = Field(default=None, min_length=2, max_length=2)
    accept_terms: bool


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class GoogleIn(BaseModel):
    id_token: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserOut(ORM):
    id: uuid.UUID
    email: str
    name: str
    uf: str | None
    role: str
    auth_provider: str
    created_at: datetime


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    uf: str | None = Field(default=None, min_length=2, max_length=2)


# --- Políticos ------------------------------------------------------------


class PoliticianSummary(BaseModel):
    id: uuid.UUID
    slug: str
    house: str
    name: str
    party: str | None
    uf: str
    photo_url: str | None
    in_office: bool


class PoliticianProfile(PoliticianSummary):
    civil_name: str
    email: str | None
    social_links: list[str]
    legislature: int | None
    official_url: str
    is_following: bool = False
    updated_at: datetime | None


class Metric(BaseModel):
    value: float | None
    house_avg: float | None


class StatsOut(BaseModel):
    period: str
    period_label: str
    attendance_rate: Metric
    sessions_total: int
    sessions_present: int
    sessions_justified: int
    sessions_absent: int
    votes_participated: Metric
    votes_total: int
    bills_authored: Metric
    bills_reported: int
    expenses_total: Metric
    computed_at: datetime | None
    methodology_url: str = "/como-calculamos"


class AgendaItem(ORM):
    id: uuid.UUID
    title: str
    organ: str | None
    location: str | None
    starts_at: datetime
    ends_at: datetime | None
    status: str | None


class BillOut(ORM):
    id: uuid.UUID
    type: str
    number: int | None
    year: int | None
    official_summary: str | None
    plain_summary: str | None
    plain_summary_ai: bool
    url: str | None


class VoteOut(BaseModel):
    id: uuid.UUID
    house: str
    voted_at: datetime
    description: str | None
    result: str | None
    yes_count: int
    no_count: int
    abstention_count: int
    bill: BillOut | None
    source_url: str


class PoliticianVote(BaseModel):
    vote: VoteOut
    choice: str
    party_orientation: str | None
    with_party: bool | None


class VoteRecordOut(BaseModel):
    politician: PoliticianSummary
    choice: str
    party_orientation: str | None
    is_followed: bool


class VoteDetail(VoteOut):
    records: list[VoteRecordOut]


class NewsOut(BaseModel):
    id: uuid.UUID
    url: str
    title: str
    snippet: str | None
    source_name: str | None
    published_at: datetime
    image_url: str | None
    politicians: list[PoliticianSummary] = []


class ExpenseCategory(BaseModel):
    category: str
    total: Decimal


class ExpensesOut(BaseModel):
    year: int
    total: Decimal
    by_category: list[ExpenseCategory]
    by_month: list[dict[str, Any]]


# --- Seguir e feed --------------------------------------------------------


class FollowPrefs(BaseModel):
    notify_votes: bool = True
    notify_agenda: bool = False
    notify_news: bool = True


class FollowOut(FollowPrefs):
    politician: PoliticianSummary
    created_at: datetime


class FeedItem(BaseModel):
    id: int
    type: str
    occurred_at: datetime
    politician: PoliticianSummary
    payload: dict[str, Any]


class CompareOut(BaseModel):
    a: PoliticianSummary
    b: PoliticianSummary
    stats_a: StatsOut
    stats_b: StatsOut
    common_votes: int
    divergent_votes: int


class IngestionRunOut(ORM):
    id: uuid.UUID
    source: str
    job: str
    started_at: datetime
    finished_at: datetime | None
    status: str
    items_upserted: int
    error: str | None

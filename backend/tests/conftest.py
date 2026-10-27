import os
import tempfile
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_tmp.name}"
os.environ["RATE_LIMIT"] = "10000/minute"
os.environ["AUTH_RATE_LIMIT"] = "10000/minute"

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    Attendance,
    AttendanceStatus,
    AuthorRole,
    Bill,
    BillAuthor,
    Expense,
    FeedEvent,
    FeedType,
    House,
    NewsArticle,
    NewsMention,
    Party,
    Politician,
    Session,
    Vote,
    VoteChoice,
    VoteRecord,
)


@pytest.fixture(autouse=True)
async def db_schema():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.fixture
async def db():
    async with SessionLocal() as s:
        yield s


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def seed(db):
    """Dois deputados e um senador fictícios, com sessões, votos e gastos."""
    pt, pl = Party(acronym="PA"), Party(acronym="PB")
    db.add_all([pt, pl])
    await db.flush()
    a = Politician(
        house=House.camara,
        external_id="1",
        civil_name="Ana Maria Souza",
        parliamentary_name="Ana Souza",
        slug="ana-souza-sp",
        party_id=pt.id,
        uf="SP",
    )
    b = Politician(
        house=House.camara,
        external_id="2",
        civil_name="Bruno Lima Costa",
        parliamentary_name="Bruno Lima",
        slug="bruno-lima-rj",
        party_id=pl.id,
        uf="RJ",
    )
    c = Politician(
        house=House.senado,
        external_id="9",
        civil_name="Carla Dias",
        parliamentary_name="Carla Dias",
        slug="carla-dias-mg",
        party_id=pt.id,
        uf="MG",
    )
    db.add_all([a, b, c])
    await db.flush()

    base = datetime(2026, 3, 10, 14, tzinfo=UTC)
    for i in range(4):
        s = Session(
            house=House.camara,
            external_id=f"s{i}",
            is_deliberative=True,
            starts_at=base + timedelta(days=i),
            type="Sessão Deliberativa",
        )
        db.add(s)
        await db.flush()
        # Ana: 3 presenças + 1 justificada; Bruno: 2 presenças + 2 faltas
        db.add(
            Attendance(
                session_id=s.id,
                politician_id=a.id,
                status=AttendanceStatus.justificada if i == 3 else AttendanceStatus.presente,
            )
        )
        db.add(
            Attendance(
                session_id=s.id,
                politician_id=b.id,
                status=AttendanceStatus.presente if i < 2 else AttendanceStatus.ausente,
            )
        )

    bill = Bill(
        house=House.camara,
        external_id="b1",
        type="PL",
        number=10,
        year=2026,
        official_summary="Dispõe sobre transparência.",
    )
    db.add(bill)
    await db.flush()
    db.add(BillAuthor(bill_id=bill.id, politician_id=a.id, role=AuthorRole.autor))
    vote = Vote(
        house=House.camara,
        external_id="v1",
        bill_id=bill.id,
        voted_at=base,
        description="Aprovado o projeto",
        result="Aprovada",
        yes_count=1,
        no_count=1,
    )
    db.add(vote)
    await db.flush()
    db.add(
        VoteRecord(
            vote_id=vote.id, politician_id=a.id, choice=VoteChoice.sim, party_orientation="sim"
        )
    )
    db.add(
        VoteRecord(
            vote_id=vote.id, politician_id=b.id, choice=VoteChoice.nao, party_orientation="sim"
        )
    )
    for p, choice in ((a, "sim"), (b, "nao")):
        db.add(
            FeedEvent(
                politician_id=p.id,
                type=FeedType.vote,
                ref_id=vote.id,
                occurred_at=base,
                payload={"title": "PL 10/2026", "choice": choice},
            )
        )
    db.add(
        Expense(
            politician_id=a.id,
            year=2026,
            month=3,
            category="Passagens",
            amount=Decimal("1000.50"),
            external_id="e1",
        )
    )
    art = NewsArticle(
        url="https://ex.com/n1",
        title="Deputada Ana Souza (PA-SP) apresenta PL",
        published_at=base,
        source_name="Exemplo",
    )
    db.add(art)
    await db.flush()
    db.add(NewsMention(article_id=art.id, politician_id=a.id, confidence=0.8))
    await db.commit()
    return {"a": a, "b": b, "c": c, "vote": vote}


async def register(client, email="eleitor@example.com") -> dict:
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "name": "Eleitor",
            "password": "senha-forte-123",
            "accept_terms": True,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def uid() -> str:
    return str(uuid.uuid4())

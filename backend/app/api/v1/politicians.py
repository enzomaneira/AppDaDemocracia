import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import and_, func, or_, select

from app.api.deps import DB, OptionalUser
from app.core.config import get_settings
from app.models import (
    AgendaEvent,
    Expense,
    Follow,
    House,
    NewsArticle,
    NewsMention,
    Party,
    Politician,
    PoliticianStats,
    Vote,
    VoteRecord,
)
from app.schemas import (
    AgendaItem,
    ExpenseCategory,
    ExpensesOut,
    Metric,
    NewsOut,
    Page,
    PoliticianProfile,
    PoliticianSummary,
    PoliticianVote,
    StatsOut,
)
from app.services.feed import decode_cursor, encode_cursor
from app.services.news_matching import normalize
from app.services.presenters import politician_official_url, politician_summary, vote_out
from app.services.stats import parse_period, unjustified_absences

router = APIRouter(prefix="/politicians", tags=["politicians"])


async def get_by_slug(db: DB, slug: str) -> Politician:
    p = (await db.execute(select(Politician).where(Politician.slug == slug))).scalar_one_or_none()
    if not p:
        raise HTTPException(404, "Político não encontrado")
    return p


@router.get("", response_model=Page[PoliticianSummary])
async def search(
    db: DB,
    q: str | None = None,
    uf: str | None = Query(None, min_length=2, max_length=2),
    party: str | None = None,
    house: House | None = None,
    in_office: bool = True,
    cursor: str | None = None,
    limit: int = Query(30, ge=1, le=100),
) -> Page[PoliticianSummary]:
    stmt = select(Politician).outerjoin(Party, Party.id == Politician.party_id)
    if in_office:
        stmt = stmt.where(Politician.in_office.is_(True))
    if q:
        # No Postgres o índice pg_trgm acelera o ILIKE; o slug cobre buscas sem acento.
        term = f"%{q.strip()}%"
        slug_term = f"%{normalize(q).replace(' ', '-')}%"
        stmt = stmt.where(
            or_(
                Politician.parliamentary_name.ilike(term),
                Politician.civil_name.ilike(term),
                Politician.slug.ilike(slug_term),
            )
        )
    if uf:
        stmt = stmt.where(Politician.uf == uf.upper())
    if party:
        stmt = stmt.where(func.upper(Party.acronym) == party.upper())
    if house:
        stmt = stmt.where(Politician.house == house)
    if cursor:
        try:
            name, last_slug = decode_cursor(cursor)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        stmt = stmt.where(Politician.slug > last_slug)
    stmt = stmt.order_by(Politician.slug).limit(limit + 1)
    rows = list((await db.execute(stmt)).scalars())
    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = encode_cursor(datetime.now(UTC), rows[-1].slug)
    return Page(items=[politician_summary(p) for p in rows], next_cursor=next_cursor)


@router.get("/{slug}", response_model=PoliticianProfile)
async def profile(slug: str, db: DB, user: OptionalUser) -> PoliticianProfile:
    p = await get_by_slug(db, slug)
    following = False
    if user:
        following = await db.get(Follow, (user.id, p.id)) is not None
    return PoliticianProfile(
        **politician_summary(p).model_dump(),
        civil_name=p.civil_name,
        email=p.email,
        social_links=p.social_links or [],
        legislature=p.legislature,
        official_url=politician_official_url(p),
        is_following=following,
        updated_at=p.updated_at,
    )


def stats_out(row: PoliticianStats | None, period_key: str, label: str) -> StatsOut:
    if row is None:
        empty = Metric(value=None, house_avg=None)
        return StatsOut(
            period=period_key, period_label=label, attendance_rate=empty, sessions_total=0,
            sessions_present=0, sessions_justified=0, sessions_absent=0,
            votes_participated=empty, votes_total=0, bills_authored=empty, bills_reported=0,
            expenses_total=empty, computed_at=None,
        )  # fmt: skip
    avg = row.house_avg or {}

    def m(value, key: str) -> Metric:
        return Metric(value=None if value is None else float(value), house_avg=avg.get(key))

    return StatsOut(
        period=period_key,
        period_label=label,
        attendance_rate=m(row.attendance_rate, "attendance_rate"),
        sessions_total=row.sessions_total,
        sessions_present=row.sessions_present,
        sessions_justified=row.sessions_justified,
        sessions_absent=unjustified_absences(
            row.sessions_total, row.sessions_present, row.sessions_justified
        ),
        votes_participated=m(row.votes_participated, "votes_participated"),
        votes_total=row.votes_total,
        bills_authored=m(row.bills_authored, "bills_authored"),
        bills_reported=row.bills_reported,
        expenses_total=m(row.expenses_total, "expenses_total"),
        computed_at=row.computed_at,
    )


async def load_stats(db: DB, p: Politician, period: str | None) -> StatsOut:
    try:
        per = parse_period(period, get_settings().legislature)
    except ValueError as e:
        raise HTTPException(400, "Período inválido: use legNN ou um ano") from e
    row = await db.get(PoliticianStats, (p.id, per.key))
    return stats_out(row, per.key, per.label)


@router.get("/{slug}/stats", response_model=StatsOut)
async def stats(slug: str, db: DB, period: str | None = None) -> StatsOut:
    return await load_stats(db, await get_by_slug(db, slug), period)


@router.get("/{slug}/agenda", response_model=list[AgendaItem])
async def agenda(
    slug: str,
    db: DB,
    from_: datetime | None = Query(None, alias="from"),
    to: datetime | None = None,
) -> list[AgendaItem]:
    p = await get_by_slug(db, slug)
    now = datetime.now(UTC)
    start = from_ or now - timedelta(days=30)
    end = to or now + timedelta(days=14)
    q = (
        select(AgendaEvent)
        .where(
            AgendaEvent.politician_id == p.id,
            AgendaEvent.starts_at >= start,
            AgendaEvent.starts_at <= end,
        )
        .order_by(AgendaEvent.starts_at.desc())
        .limit(200)
    )
    return [AgendaItem.model_validate(e) for e in (await db.execute(q)).scalars()]


@router.get("/{slug}/votes", response_model=Page[PoliticianVote])
async def votes(
    slug: str, db: DB, cursor: str | None = None, limit: int = Query(20, ge=1, le=100)
) -> Page[PoliticianVote]:
    p = await get_by_slug(db, slug)
    q = (
        select(VoteRecord, Vote)
        .join(Vote, Vote.id == VoteRecord.vote_id)
        .where(VoteRecord.politician_id == p.id)
    )
    if cursor:
        try:
            t, last = decode_cursor(cursor)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        q = q.where(or_(Vote.voted_at < t, and_(Vote.voted_at == t, Vote.id < uuid.UUID(last))))
    q = q.order_by(Vote.voted_at.desc(), Vote.id.desc()).limit(limit + 1)
    rows = (await db.execute(q)).all()
    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = encode_cursor(rows[-1][1].voted_at, rows[-1][1].id)
    items = []
    for rec, v in rows:
        orient = rec.party_orientation
        with_party = None
        if orient and orient.lower() in {"sim", "nao", "abstencao", "obstrucao"}:
            with_party = rec.choice.value == orient.lower()
        items.append(
            PoliticianVote(
                vote=vote_out(v),
                choice=rec.choice.value,
                party_orientation=orient,
                with_party=with_party,
            )
        )
    return Page(items=items, next_cursor=next_cursor)


async def news_page(
    db: DB, politician_ids: list[uuid.UUID], cursor: str | None, limit: int
) -> Page[NewsOut]:
    if not politician_ids:
        return Page(items=[])
    q = (
        select(NewsArticle)
        .join(NewsMention, NewsMention.article_id == NewsArticle.id)
        .where(NewsMention.politician_id.in_(politician_ids))
        .distinct()
    )
    if cursor:
        t, last = decode_cursor(cursor)
        q = q.where(
            or_(
                NewsArticle.published_at < t,
                and_(NewsArticle.published_at == t, NewsArticle.id < uuid.UUID(last)),
            )
        )
    q = q.order_by(NewsArticle.published_at.desc(), NewsArticle.id.desc()).limit(limit + 1)
    arts = list((await db.execute(q)).scalars())
    next_cursor = None
    if len(arts) > limit:
        arts = arts[:limit]
        next_cursor = encode_cursor(arts[-1].published_at, arts[-1].id)

    mentions: dict[uuid.UUID, list[PoliticianSummary]] = {}
    if arts:
        mq = (
            select(NewsMention.article_id, Politician)
            .join(Politician, Politician.id == NewsMention.politician_id)
            .where(
                NewsMention.article_id.in_([a.id for a in arts]),
                NewsMention.politician_id.in_(politician_ids),
            )
        )
        for aid, pol in (await db.execute(mq)).all():
            mentions.setdefault(aid, []).append(politician_summary(pol))
    return Page(
        items=[
            NewsOut(
                id=a.id, url=a.url, title=a.title, snippet=a.snippet, source_name=a.source_name,
                published_at=a.published_at, image_url=a.image_url,
                politicians=mentions.get(a.id, []),
            )
            for a in arts
        ],
        next_cursor=next_cursor,
    )  # fmt: skip


@router.get("/{slug}/news", response_model=Page[NewsOut])
async def news(
    slug: str, db: DB, cursor: str | None = None, limit: int = Query(20, ge=1, le=100)
) -> Page[NewsOut]:
    p = await get_by_slug(db, slug)
    try:
        return await news_page(db, [p.id], cursor, limit)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.get("/{slug}/expenses", response_model=ExpensesOut)
async def expenses(slug: str, db: DB, year: int | None = None) -> ExpensesOut:
    p = await get_by_slug(db, slug)
    year = year or datetime.now(UTC).year
    base = select().where(Expense.politician_id == p.id, Expense.year == year)
    by_cat = await db.execute(
        base.add_columns(Expense.category, func.sum(Expense.amount).label("total"))
        .group_by(Expense.category)
        .order_by(func.sum(Expense.amount).desc())
    )
    cats = [ExpenseCategory(category=c, total=t) for c, t in by_cat.all()]
    by_month = await db.execute(
        base.add_columns(Expense.month, func.sum(Expense.amount))
        .group_by(Expense.month)
        .order_by(Expense.month)
    )
    return ExpensesOut(
        year=year,
        total=sum((c.total for c in cats), start=0),
        by_category=cats,
        by_month=[{"month": m, "total": float(t)} for m, t in by_month.all()],
    )

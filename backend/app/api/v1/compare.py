"""Comparação lado a lado de dois parlamentares (RF14), no estilo "comparar atletas".

Neutra por construção: mostra os números e a média da casa de cada um, sem eleger
"melhor". Votos só se comparam entre parlamentares da mesma casa (cada casa vota as
suas matérias) e só quando os dois deram voto público.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import Select, and_, case, func, or_, select
from sqlalchemy.orm import aliased

from app.api.deps import DB
from app.api.v1.politicians import get_by_slug, load_stats
from app.core.config import get_settings
from app.models import Politician, Vote, VoteChoice, VoteRecord
from app.schemas import CompareOut, CompareVote, Page
from app.services.feed import decode_cursor, encode_cursor
from app.services.presenters import politician_summary, vote_out
from app.services.stats import parse_period

router = APIRouter(prefix="/compare", tags=["compare"])

PUBLIC_CHOICES = (VoteChoice.sim, VoteChoice.nao, VoteChoice.abstencao, VoteChoice.obstrucao)


def agreement_rate(common: int, divergent: int) -> float | None:
    if common <= 0:
        return None
    return round((common - divergent) / common * 100, 1)


async def _pair(db: DB, a: str, b: str) -> tuple[Politician, Politician]:
    if a == b:
        raise HTTPException(400, "Escolha dois parlamentares diferentes")
    return await get_by_slug(db, a), await get_by_slug(db, b)


def _period_bounds(period: str | None) -> tuple[datetime, datetime]:
    try:
        p = parse_period(period, get_settings().legislature)
    except ValueError as e:
        raise HTTPException(400, "Período inválido: use legNN ou um ano") from e
    return p.start, p.end


def _common_votes(pa: Politician, pb: Politician, period: str | None):
    """Votações em que os dois deram voto público, no período: (Vote, escolha A, escolha B)."""
    ra, rb = aliased(VoteRecord), aliased(VoteRecord)
    start, end = _period_bounds(period)
    q: Select = (
        select(Vote, ra.choice.label("a"), rb.choice.label("b"))
        .join(ra, ra.vote_id == Vote.id)
        .join(rb, rb.vote_id == Vote.id)
        .where(
            ra.politician_id == pa.id,
            rb.politician_id == pb.id,
            ra.choice.in_(PUBLIC_CHOICES),
            rb.choice.in_(PUBLIC_CHOICES),
            Vote.voted_at >= start,
            Vote.voted_at < end,
        )
    )
    return q, ra, rb


@router.get("", response_model=CompareOut)
async def compare(db: DB, a: str, b: str, period: str | None = None) -> CompareOut:
    pa, pb = await _pair(db, a, b)
    q, ra, rb = _common_votes(pa, pb, period)
    totals = q.with_only_columns(
        func.count(), func.sum(case((ra.choice != rb.choice, 1), else_=0))
    ).order_by(None)
    common, divergent = (await db.execute(totals)).one()
    common, divergent = common or 0, int(divergent or 0)
    return CompareOut(
        a=politician_summary(pa),
        b=politician_summary(pb),
        stats_a=await load_stats(db, pa, period),
        stats_b=await load_stats(db, pb, period),
        same_house=pa.house == pb.house,
        common_votes=common,
        divergent_votes=divergent,
        agreement_rate=agreement_rate(common, divergent),
    )


@router.get("/votes", response_model=Page[CompareVote])
async def compare_votes(
    db: DB,
    a: str,
    b: str,
    period: str | None = None,
    divergent: bool = False,
    cursor: str | None = None,
    limit: int = Query(20, ge=1, le=100),
) -> Page[CompareVote]:
    """Votações em comum, mais recentes primeiro; `divergent=true` mostra só as discordâncias."""
    pa, pb = await _pair(db, a, b)
    q, ra, rb = _common_votes(pa, pb, period)
    if divergent:
        q = q.where(ra.choice != rb.choice)
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
        next_cursor = encode_cursor(rows[-1][0].voted_at, rows[-1][0].id)
    return Page(
        items=[
            CompareVote(vote=vote_out(v), choice_a=ca.value, choice_b=cb.value, agree=ca == cb)
            for v, ca, cb in rows
        ],
        next_cursor=next_cursor,
    )

"""Proposições de cada parlamentar, com link para a ficha oficial de tramitação.

Mesmo critério da métrica "proposições apresentadas": só projetos (STATS_BILL_TYPES) em
que o parlamentar é autor ou coautor. As fontes não distinguem o autor principal dos
coautores na listagem, então a página não faz essa distinção.
"""

import base64
import re

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from app.api.deps import DB
from app.api.v1.politicians import get_by_slug
from app.models import AuthorRole, Bill, BillAuthor
from app.schemas import BillOut, BillsPage
from app.services.presenters import bill_url
from app.services.stats import STATS_BILL_TYPES

router = APIRouter(prefix="/politicians", tags=["politicians"])

# "PL 2036/2023", "2036/2023" ou só "2036"
NUMBER_RE = re.compile(r"^\s*(?:([A-Za-z]+)\s+)?(\d+)(?:\s*/\s*(\d{4}))?\s*$")


def _encode(offset: int) -> str:
    return base64.urlsafe_b64encode(f"o:{offset}".encode()).decode().rstrip("=")


def _decode(cursor: str) -> int:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
        kind, value = raw.split(":", 1)
        if kind != "o" or int(value) < 0:
            raise ValueError
        return int(value)
    except (ValueError, UnicodeDecodeError) as e:
        raise HTTPException(400, "cursor inválido") from e


@router.get("/{slug}/bills", response_model=BillsPage)
async def politician_bills(
    slug: str,
    db: DB,
    type: str | None = Query(None, description="PL, PLP, PEC, PDL, PRC ou PRS"),
    q: str | None = Query(None, max_length=200, description="texto da ementa ou número"),
    cursor: str | None = None,
    limit: int = Query(20, ge=1, le=100),
) -> BillsPage:
    p = await get_by_slug(db, slug)
    if type and type.upper() not in STATS_BILL_TYPES:
        raise HTTPException(400, f"Tipo inválido; use um de: {', '.join(STATS_BILL_TYPES)}")

    base = (
        select(Bill)
        .join(BillAuthor, BillAuthor.bill_id == Bill.id)
        .where(
            BillAuthor.politician_id == p.id,
            BillAuthor.role == AuthorRole.autor,
            Bill.type.in_(STATS_BILL_TYPES),
        )
    )
    if q and q.strip():
        m = NUMBER_RE.match(q)
        if m:  # busca por número, com tipo e ano opcionais
            tipo, numero, ano = m.groups()
            base = base.where(Bill.number == int(numero))
            if ano:
                base = base.where(Bill.year == int(ano))
            if tipo:
                base = base.where(Bill.type == tipo.upper())
        else:
            base = base.where(Bill.official_summary.ilike(f"%{q.strip()}%"))

    sub = base.subquery()
    by_type = dict((await db.execute(select(sub.c.type, func.count()).group_by(sub.c.type))).all())

    filtered = base.where(Bill.type == type.upper()) if type else base
    total = (await db.execute(select(func.count()).select_from(filtered.subquery()))).scalar_one()

    offset = _decode(cursor) if cursor else 0
    rows = (
        await db.execute(
            filtered.order_by(
                Bill.year.desc().nulls_last(), Bill.number.desc().nulls_last(), Bill.id
            )
            .offset(offset)
            .limit(limit + 1)
        )
    ).scalars()
    items = list(rows)
    next_cursor = _encode(offset + limit) if len(items) > limit else None
    return BillsPage(
        # Todo item leva à ficha oficial: se o link não foi gravado, ele sai do código da fonte.
        items=[
            BillOut.model_validate(b).model_copy(
                update={"url": b.url or bill_url(b.house, b.external_id)}
            )
            for b in items[:limit]
        ],
        next_cursor=next_cursor,
        total=total,
        by_type=by_type,
    )

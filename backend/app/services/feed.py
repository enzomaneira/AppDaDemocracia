"""Feed dos seguidos (RF05): uma única consulta em feed_events, paginada por cursor."""

from __future__ import annotations

import base64
import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FeedEvent, FeedType

PAGE_SIZE = 30


def encode_cursor(occurred_at: datetime, item_id: Any) -> str:
    raw = json.dumps({"t": occurred_at.isoformat(), "id": str(item_id)})
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, str]:
    padded = cursor + "=" * (-len(cursor) % 4)
    try:
        data = json.loads(base64.urlsafe_b64decode(padded))
        return datetime.fromisoformat(data["t"]), str(data["id"])
    except (ValueError, KeyError, json.JSONDecodeError) as e:
        raise ValueError("cursor inválido") from e


async def add_event(
    db: AsyncSession,
    politician_id: uuid.UUID,
    type_: FeedType,
    ref_id: uuid.UUID,
    occurred_at: datetime,
    payload: dict[str, Any],
) -> None:
    db.add(
        FeedEvent(
            politician_id=politician_id,
            type=type_,
            ref_id=ref_id,
            occurred_at=occurred_at,
            payload=payload,
        )
    )


async def query_feed(
    db: AsyncSession,
    politician_ids: list[uuid.UUID],
    type_: FeedType | None = None,
    cursor: str | None = None,
    limit: int = PAGE_SIZE,
) -> tuple[list[FeedEvent], str | None]:
    if not politician_ids:
        return [], None
    q = select(FeedEvent).where(FeedEvent.politician_id.in_(politician_ids))
    if type_:
        q = q.where(FeedEvent.type == type_)
    if cursor:
        t, last_id = decode_cursor(cursor)
        q = q.where(
            or_(
                FeedEvent.occurred_at < t,
                and_(FeedEvent.occurred_at == t, FeedEvent.id < int(last_id)),
            )
        )
    q = q.order_by(FeedEvent.occurred_at.desc(), FeedEvent.id.desc()).limit(limit + 1)
    items = list((await db.execute(q)).scalars())
    next_cursor = None
    if len(items) > limit:
        items = items[:limit]
        next_cursor = encode_cursor(items[-1].occurred_at, items[-1].id)
    return items, next_cursor

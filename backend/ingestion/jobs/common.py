"""Utilitários dos jobs: registro em ingestion_runs, upsert idempotente e slug."""

from __future__ import annotations

import logging
import re
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import SessionLocal
from app.models import House, IngestionRun, Party, Politician
from app.services.news_matching import normalize

log = logging.getLogger("ingestion")
M = TypeVar("M")


@dataclass
class RunCounter:
    items: int = 0


@asynccontextmanager
async def tracked(job: str, source: str):
    """Registra início/fim/erro do job. Uma falha é registrada e não interrompe os demais."""
    async with SessionLocal() as db:
        run = IngestionRun(job=job, source=source, started_at=datetime.now(UTC))
        db.add(run)
        await db.commit()
        run_id = run.id
    counter = RunCounter()
    log.info("job start", extra={"extra": {"job": job, "source": source}})
    try:
        yield counter
        status, error = "ok", None
    except Exception as e:  # noqa: BLE001
        log.exception("job failed", extra={"extra": {"job": job, "source": source}})
        status, error = "error", f"{type(e).__name__}: {e}"[:2000]
    async with SessionLocal() as db:
        run = await db.get(IngestionRun, run_id)
        assert run
        run.finished_at = datetime.now(UTC)
        run.status = status
        run.items_upserted = counter.items
        run.error = error
        await db.commit()
    log.info(
        "job end",
        extra={"extra": {"job": job, "status": status, "items": counter.items}},
    )


async def upsert(
    db: AsyncSession,
    model: type[M],
    keys: dict[str, Any],
    values: dict[str, Any],
    on_create: dict[str, Any] | None = None,
) -> tuple[M, bool]:
    """Busca por `keys`; atualiza ou cria (com `on_create` extra). Retorna (objeto, criado?)."""
    q = select(model).filter_by(**keys)
    obj = (await db.execute(q)).scalar_one_or_none()
    if obj is None:
        obj = model(**keys, **values, **(on_create or {}))
        db.add(obj)
        await db.flush()
        return obj, True
    for k, v in values.items():
        setattr(obj, k, v)
    return obj, False


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", normalize(text)).strip("-")


async def unique_slug(db: AsyncSession, name: str, uf: str, external_id: str) -> str:
    base = f"{slugify(name)}-{uf.lower()}"
    exists = (await db.execute(select(Politician.id).where(Politician.slug == base))).first()
    return f"{base}-{external_id}" if exists else base


async def party_id(
    db: AsyncSession, acronym: str | None, cache: dict[str, uuid.UUID]
) -> uuid.UUID | None:
    if not acronym:
        return None
    acronym = acronym.strip().upper()
    if acronym not in cache:
        party, _ = await upsert(db, Party, {"acronym": acronym}, {})
        cache[acronym] = party.id
    return cache[acronym]


async def politician_index(db: AsyncSession, house: House) -> dict[str, Politician]:
    """external_id → Politician de uma casa."""
    rows = (await db.execute(select(Politician).where(Politician.house == house))).scalars()
    return {p.external_id: p for p in rows}


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        # Horários das fontes oficiais estão em Brasília (UTC-3).
        from zoneinfo import ZoneInfo

        dt = dt.replace(tzinfo=ZoneInfo("America/Sao_Paulo"))
    return dt.astimezone(UTC)

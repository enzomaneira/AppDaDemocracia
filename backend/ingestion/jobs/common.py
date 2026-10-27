"""Utilitários dos jobs: registro em ingestion_runs, upsert idempotente e slug."""

from __future__ import annotations

import logging
import re
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import House, IngestionRun, Party, Politician
from app.services.news_matching import normalize
from app.services.stats import legislature_start_year

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


def sync_start(latest: datetime | None) -> date:
    """Início da janela incremental de um job.

    Continua de onde o banco parou (último item gravado, menos SYNC_DAYS_BACK de folga para
    pegar correções da fonte). Banco vazio → carga desde o início da legislatura.
    SYNC_SINCE (ou `run_daily --since`) força a data.
    """
    s = get_settings()
    if s.sync_since:
        return s.sync_since
    if latest is None:
        return date(legislature_start_year(s.legislature), 2, 1)
    return min(latest.date(), datetime.now(UTC).date()) - timedelta(days=s.sync_days_back)


def date_chunks(start: date, end: date, max_days: int = 90) -> list[tuple[date, date]]:
    """Fatia [start, end] em blocos (a API da Câmara aceita no máximo 3 meses por consulta)."""
    out = []
    cur = start
    while cur <= end:
        stop = min(cur + timedelta(days=max_days - 1), end)
        out.append((cur, stop))
        cur = stop + timedelta(days=1)
    return out


def in_exercise(p: Politician, when: datetime) -> bool:
    """O parlamentar estava em exercício nessa data?

    Usa os períodos do histórico oficial quando existem (suplentes, licenças, vacâncias);
    sem histórico, cai para a situação atual.
    """
    periods = p.office_periods or []
    if not periods:
        return p.in_office
    day = when.date().isoformat()
    return any(start <= day and (end is None or day < end) for start, end in periods)


def feed_worthy(when: datetime) -> bool:
    """Só eventos recentes viram item de feed; a carga histórica não inunda o feed."""
    return when >= datetime.now(UTC) - timedelta(days=get_settings().feed_max_age_days)


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        # Horários das fontes oficiais estão em Brasília (UTC-3).
        from zoneinfo import ZoneInfo

        dt = dt.replace(tzinfo=ZoneInfo("America/Sao_Paulo"))
    return dt.astimezone(UTC)

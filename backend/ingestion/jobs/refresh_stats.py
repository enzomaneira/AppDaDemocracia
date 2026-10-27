"""7 · Recalcula politician_stats (legislatura atual e ano corrente)."""

from __future__ import annotations

from datetime import UTC, datetime

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.stats import compute_all, parse_period
from ingestion.jobs.common import tracked


async def run() -> None:
    leg = get_settings().legislature
    periods = [f"leg{leg}", str(datetime.now(UTC).year)]
    async with tracked("refresh_stats", "db") as run_, SessionLocal() as db:
        for key in periods:
            run_.items += await compute_all(db, parse_period(key, leg))

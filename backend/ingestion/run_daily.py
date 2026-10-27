"""Entrypoint do Cron Job diário (Railway: `0 6 * * *` UTC = 03h em Brasília).

O container sobe, roda os jobs em sequência e encerra. Cada job é idempotente e
registra sua execução em ingestion_runs; a falha de um não impede os seguintes.

Uso:
    python -m ingestion.run_daily              # todos os jobs
    python -m ingestion.run_daily votes news   # só alguns
"""

from __future__ import annotations

import asyncio
import sys

from app.core.config import get_settings
from app.core.logging import setup_logging
from ingestion.jobs import (
    refresh_stats,
    sync_agenda,
    sync_bills,
    sync_expenses,
    sync_news,
    sync_politicians,
    sync_votes,
)
from ingestion.sources.camara import CamaraSource
from ingestion.sources.senado import SenadoSource

ORDER = ["politicians", "votes", "agenda", "bills", "expenses", "news", "stats"]


async def main(selected: list[str]) -> None:
    camara, senado = CamaraSource(), SenadoSource()
    jobs = {
        "politicians": lambda: sync_politicians.run(camara, senado),
        "votes": lambda: sync_votes.run(camara, senado),
        "agenda": lambda: sync_agenda.run(camara),
        "bills": lambda: sync_bills.run(camara),
        "expenses": lambda: sync_expenses.run(camara, senado),
        "news": sync_news.run,
        "stats": refresh_stats.run,
    }
    try:
        for name in ORDER:
            if not selected or name in selected:
                await jobs[name]()
    finally:
        await camara.aclose()
        await senado.aclose()


if __name__ == "__main__":
    setup_logging(get_settings().log_level)
    unknown = set(sys.argv[1:]) - set(ORDER)
    if unknown:
        sys.exit(f"Jobs desconhecidos: {', '.join(unknown)}. Opções: {', '.join(ORDER)}")
    asyncio.run(main(sys.argv[1:]))

"""Entrypoint do Cron Job diário (Railway: `0 6 * * *` UTC = 03h em Brasília).

O container sobe, roda os jobs em sequência e encerra. Cada job é idempotente e
registra sua execução em ingestion_runs; a falha de um não impede os seguintes.

Uso:
    python -m ingestion.run_daily              # todos os jobs
    python -m ingestion.run_daily votes news   # só alguns
    python -m ingestion.run_daily --since 2023-02-01   # recarga desde uma data

Sem --since, cada job continua de onde o banco parou; com o banco vazio, carrega a
legislatura atual inteira.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date

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
        "bills": lambda: sync_bills.run(camara, senado),
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


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Sincronização diária com as fontes oficiais.")
    p.add_argument("jobs", nargs="*", choices=[[], *ORDER], help="jobs a rodar (padrão: todos)")
    p.add_argument(
        "--since",
        type=date.fromisoformat,
        help="recarrega desde esta data (AAAA-MM-DD), em vez de continuar de onde o banco parou",
    )
    return p.parse_args(argv)


if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    settings = get_settings()
    if args.since:
        settings.sync_since = args.since
    setup_logging(settings.log_level)
    jobs = args.jobs or [j.strip() for j in settings.sync_jobs.split(",") if j.strip()]
    unknown = set(jobs) - set(ORDER)
    if unknown:
        sys.exit(f"Jobs desconhecidos em SYNC_JOBS: {', '.join(unknown)}")
    asyncio.run(main(jobs))

"""4 · Proposições de autoria (Câmara e Senado): só projetos, gravados em lote.

As APIs chamam de "proposição" também requerimentos, pareceres e documentos de tramitação
(um deputado chega a ter dezenas de milhares). Para a métrica "proposições apresentadas"
contam só os projetos (STATS_BILL_TYPES), de autoria ou coautoria.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select, update

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import AuthorRole, Bill, BillAuthor, House, Politician
from app.services.presenters import bill_url
from app.services.stats import STATS_BILL_TYPES, legislature_start_year
from ingestion.jobs.common import parse_dt, politician_index, tracked
from ingestion.sources import senado as sen
from ingestion.sources.camara import CamaraSource

log = logging.getLogger("ingestion.bills")
COMMIT_EVERY = 2000


def bill_label(bill: Bill) -> str:
    """'PL 10/2026'; documentos acessórios vêm com número/ano zerados e ficam só com o tipo."""
    return f"{bill.type} {bill.number}/{bill.year}" if bill.number and bill.year else bill.type


async def _window(db, house: House) -> tuple[date, dict[str, Politician]]:
    """(início, parlamentares a consultar) para a casa.

    A lista de proposições não traz uma data confiável para continuar de onde parou; sem
    histórico na casa, carrega a legislatura inteira.
    """
    s = get_settings()
    today = datetime.now(UTC).date()
    has_bills = (
        await db.execute(
            select(BillAuthor.bill_id)
            .join(Politician, Politician.id == BillAuthor.politician_id)
            .where(Politician.house == house)
            .limit(1)
        )
    ).first() is not None
    start = s.sync_since or (
        today - timedelta(days=s.sync_days_back)
        if has_bills
        else date(legislature_start_year(s.legislature), 2, 1)
    )
    pols = await politician_index(db, house)
    if has_bills and not s.sync_since:
        pols = {k: p for k, p in pols.items() if p.in_office}
    return start, pols


async def _fetch_all(
    pols: dict[str, Politician], fetch: Callable[[str], Awaitable[list[dict]]]
) -> list[tuple[str, list[dict]]]:
    async def one(ext: str):
        try:
            return ext, await fetch(ext)
        except Exception as err:  # noqa: BLE001 — um parlamentar com erro não derruba o job
            log.warning("proposições de %s ignoradas: %s", ext, err)
            return ext, []

    return await asyncio.gather(*(one(e) for e in pols))


async def _save_bills(db, house: House, pols, results: list[tuple[str, list[dict]]]) -> int:
    """Grava em lote: o que já existe é carregado uma vez, em vez de 2 consultas por item.

    Cada item: {"external_id", "type", "number", "year", "official_summary", "presented_at"}.
    Os itens de feed saem depois, do banco (sync_feed), com a data de apresentação.
    """
    known = (
        await db.execute(
            select(Bill.external_id, Bill.id, Bill.presented_at).where(Bill.house == house)
        )
    ).all()
    bill_ids: dict[str, uuid.UUID] = {ext: bid for ext, bid, _ in known}
    undated = {bid for _, bid, when in known if when is None}
    dates: dict[uuid.UUID, object] = {}  # projetos já gravados que ganham a data agora
    links = set(
        (
            await db.execute(
                select(BillAuthor.bill_id, BillAuthor.politician_id).where(
                    BillAuthor.role == AuthorRole.autor
                )
            )
        ).all()
    )
    pending = n = 0
    for ext, items in results:
        p = pols[ext]
        for it in items:
            if it["type"] not in STATS_BILL_TYPES:
                continue
            bext = it["external_id"]
            bill_id = bill_ids.get(bext)
            if bill_id is None:
                bill = Bill(
                    id=uuid.uuid4(),
                    house=house,
                    url=bill_url(house, bext),
                    **it,
                )
                db.add(bill)
                bill_id = bill_ids[bext] = bill.id
                pending += 1
            elif bill_id in undated and it.get("presented_at"):
                dates[bill_id] = it["presented_at"]
                undated.discard(bill_id)
            if (bill_id, p.id) in links:
                continue
            links.add((bill_id, p.id))
            db.add(BillAuthor(bill_id=bill_id, politician_id=p.id, role=AuthorRole.autor))
            pending += 1
            n += 1
            if pending >= COMMIT_EVERY:
                await db.commit()
                pending = 0
    # Atualização em lote por chave primária (projetos carregados antes de existir a coluna).
    rows = [{"id": bid, "presented_at": when} for bid, when in dates.items()]
    for i in range(0, len(rows), COMMIT_EVERY):
        await db.execute(update(Bill), rows[i : i + COMMIT_EVERY])
    await db.commit()
    return n


async def sync_camara(api: CamaraSource) -> None:
    async with tracked("sync_bills", "camara") as run, SessionLocal() as db:
        start, pols = await _window(db, House.camara)

        async def fetch(ext: str) -> list[dict]:
            # Filtra os tipos já na API: sem isso vêm dezenas de milhares de requerimentos.
            return [
                {
                    "external_id": str(b["id"]),
                    "type": b.get("siglaTipo") or "PROP",
                    "number": b.get("numero"),
                    "year": b.get("ano"),
                    "official_summary": b.get("ementa"),
                    "presented_at": parse_dt(b.get("dataApresentacao")),
                }
                async for b in api.proposicoes_autor(ext, start, STATS_BILL_TYPES)
            ]

        results = await _fetch_all(pols, fetch)
        run.items += await _save_bills(db, House.camara, pols, results)


async def sync_senado(api: sen.SenadoSource) -> None:
    async with tracked("sync_bills", "senado") as run, SessionLocal() as db:
        start, pols = await _window(db, House.senado)

        async def fetch(ext: str) -> list[dict]:
            # /processo devolve tudo de uma vez; o tipo sai da identificação ("PL 2036/2023").
            return [
                it for it in map(sen.parse_processo, await api.processos_autor(ext, start)) if it
            ]

        results = await _fetch_all(pols, fetch)
        run.items += await _save_bills(db, House.senado, pols, results)


async def run(camara: CamaraSource, senado: sen.SenadoSource) -> None:
    await sync_camara(camara)
    await sync_senado(senado)

"""4 · Proposições de autoria (Câmara): só projetos, gravados em lote.

A API chama de "proposição" também requerimentos, pareceres e documentos de tramitação
(um deputado chega a ter dezenas de milhares). Para a métrica "proposições apresentadas"
contam só os projetos (STATS_BILL_TYPES), filtrados já na consulta à API.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import AuthorRole, Bill, BillAuthor, FeedType, House
from app.services.feed import add_event
from app.services.presenters import bill_url
from app.services.stats import STATS_BILL_TYPES, legislature_start_year
from ingestion.jobs.common import politician_index, tracked
from ingestion.sources.camara import CamaraSource

log = logging.getLogger("ingestion.bills")
COMMIT_EVERY = 2000


def bill_label(bill: Bill) -> str:
    """'PL 10/2026'; documentos acessórios vêm com número/ano zerados e ficam só com o tipo."""
    return f"{bill.type} {bill.number}/{bill.year}" if bill.number and bill.year else bill.type


async def sync_camara(api: CamaraSource) -> None:
    s = get_settings()
    today = datetime.now(UTC).date()
    async with tracked("sync_bills", "camara") as run, SessionLocal() as db:
        has_bills = (await db.execute(select(BillAuthor.bill_id).limit(1))).first() is not None
        # A lista de proposições não traz data; sem histórico, carrega a legislatura inteira.
        start = s.sync_since or (
            today - timedelta(days=s.sync_days_back)
            if has_bills
            else date(legislature_start_year(s.legislature), 2, 1)
        )
        # Numa carga histórica, proposições antigas não viram item de feed.
        to_feed = start >= today - timedelta(days=s.feed_max_age_days)
        pols = await politician_index(db, House.camara)
        if has_bills and not s.sync_since:
            pols = {k: p for k, p in pols.items() if p.in_office}

        async def fetch(ext: str):
            try:
                return ext, [b async for b in api.proposicoes_autor(ext, start, STATS_BILL_TYPES)]
            except Exception as err:  # noqa: BLE001 — um deputado com erro não derruba o job
                log.warning("proposições do deputado %s ignoradas: %s", ext, err)
                return ext, []

        results = await asyncio.gather(*(fetch(e) for e in pols))

        # Gravação em lote: o que já existe é carregado uma vez, em vez de 2 consultas por item.
        bill_ids: dict[str, uuid.UUID] = dict(
            (await db.execute(select(Bill.external_id, Bill.id).where(Bill.house == House.camara)))
            .tuples()
            .all()
        )
        links = set(
            (
                await db.execute(
                    select(BillAuthor.bill_id, BillAuthor.politician_id).where(
                        BillAuthor.role == AuthorRole.autor
                    )
                )
            )
            .tuples()
            .all()
        )
        pending = 0
        for ext, props in results:
            p = pols[ext]
            for b in props:
                bext = str(b["id"])
                bill_id = bill_ids.get(bext)
                if bill_id is None:
                    bill = Bill(
                        id=uuid.uuid4(),
                        house=House.camara,
                        external_id=bext,
                        type=b.get("siglaTipo") or "PROP",
                        number=b.get("numero"),
                        year=b.get("ano"),
                        official_summary=b.get("ementa"),
                        url=bill_url(House.camara, bext),
                    )
                    db.add(bill)
                    bill_id = bill_ids[bext] = bill.id
                    pending += 1
                if (bill_id, p.id) in links:
                    continue
                links.add((bill_id, p.id))
                db.add(BillAuthor(bill_id=bill_id, politician_id=p.id, role=AuthorRole.autor))
                pending += 1
                run.items += 1
                if to_feed:
                    label = f"{b.get('siglaTipo')} {b.get('numero')}/{b.get('ano')}"
                    await add_event(
                        db, p.id, FeedType.bill, bill_id, datetime.now(UTC),
                        {"title": (b.get("ementa") or "")[:300], "bill": label,
                         "url": bill_url(House.camara, bext)},
                    )  # fmt: skip
                if pending >= COMMIT_EVERY:
                    await db.commit()
                    pending = 0
        await db.commit()


async def run(camara: CamaraSource) -> None:
    await sync_camara(camara)

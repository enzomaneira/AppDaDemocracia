"""4 · Proposições de autoria e pareceres de relatoria (Câmara)."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import AuthorRole, Bill, BillAuthor, FeedType, House
from app.services.feed import add_event
from app.services.presenters import bill_url
from app.services.stats import legislature_start_year
from ingestion.jobs.common import politician_index, tracked, upsert
from ingestion.sources.camara import CamaraSource

log = logging.getLogger("ingestion.bills")

# Pareceres aparecem como "autoria" do relator na API; contam como relatoria.
RELATOR_TYPES = {"PRL", "PPP", "PAR", "PRLP", "PRLE"}


def author_role(bill_type: str) -> AuthorRole:
    return AuthorRole.relator if bill_type.upper() in RELATOR_TYPES else AuthorRole.autor


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
                return ext, [b async for b in api.proposicoes_autor(ext, start)]
            except Exception as err:  # noqa: BLE001 — um deputado com erro não derruba o job
                log.warning("proposições do deputado %s ignoradas: %s", ext, err)
                return ext, []

        for ext, props in await asyncio.gather(*(fetch(e) for e in pols)):
            p = pols[ext]
            for b in props:
                bill, _ = await upsert(
                    db,
                    Bill,
                    {"house": House.camara, "external_id": str(b["id"])},
                    {
                        "type": b.get("siglaTipo") or "PROP",
                        "number": b.get("numero"),
                        "year": b.get("ano"),
                        "official_summary": b.get("ementa"),
                        "url": bill_url(House.camara, str(b["id"])),
                    },
                )
                role = author_role(bill.type)
                link = await db.execute(
                    select(BillAuthor).filter_by(bill_id=bill.id, politician_id=p.id, role=role)
                )
                link_missing = link.scalar_one_or_none() is None
                if link_missing:
                    db.add(BillAuthor(bill_id=bill.id, politician_id=p.id, role=role))
                if link_missing and to_feed:
                    await add_event(
                        db, p.id, FeedType.bill, bill.id, datetime.now(UTC),
                        {"title": (b.get("ementa") or "")[:300], "bill": bill_label(bill),
                         "role": role.value, "url": bill.url},
                    )  # fmt: skip
                run.items += 1
        await db.commit()


async def run(camara: CamaraSource) -> None:
    await sync_camara(camara)

"""4 · Proposições de autoria e pareceres de relatoria (Câmara)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import AuthorRole, Bill, BillAuthor, FeedType, House
from app.services.feed import add_event
from app.services.presenters import bill_url
from ingestion.jobs.common import politician_index, tracked, upsert
from ingestion.sources.camara import CamaraSource

# Pareceres aparecem como "autoria" do relator na API; contam como relatoria.
RELATOR_TYPES = {"PRL", "PPP", "PAR", "PRLP", "PRLE"}


def author_role(bill_type: str) -> AuthorRole:
    return AuthorRole.relator if bill_type.upper() in RELATOR_TYPES else AuthorRole.autor


def bill_label(bill: Bill) -> str:
    """'PL 10/2026'; documentos acessórios vêm com número/ano zerados e ficam só com o tipo."""
    return f"{bill.type} {bill.number}/{bill.year}" if bill.number and bill.year else bill.type


async def sync_camara(api: CamaraSource) -> None:
    s = get_settings()
    start = datetime.now(UTC).date() - timedelta(days=s.sync_days_back)
    async with tracked("sync_bills", "camara") as run, SessionLocal() as db:
        pols = {k: p for k, p in (await politician_index(db, House.camara)).items() if p.in_office}

        async def fetch(ext: str):
            return ext, [b async for b in api.proposicoes_autor(ext, start)]

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
                if link.scalar_one_or_none() is None:
                    db.add(BillAuthor(bill_id=bill.id, politician_id=p.id, role=role))
                    await add_event(
                        db, p.id, FeedType.bill, bill.id, datetime.now(UTC),
                        {"title": (b.get("ementa") or "")[:300], "bill": bill_label(bill),
                         "role": role.value, "url": bill.url},
                    )  # fmt: skip
                run.items += 1
        await db.commit()


async def run(camara: CamaraSource) -> None:
    await sync_camara(camara)

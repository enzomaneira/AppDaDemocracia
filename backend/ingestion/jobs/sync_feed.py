"""7 · Reconcilia os itens de feed de proposições e agenda a partir do banco.

Votos e notícias geram o item de feed na hora (têm data certa e são sempre novos). Já
proposições e agenda vinham com dois problemas quando o item nascia durante a sincronização:
a carga histórica não gerava nada, a agenda só gerava para eventos novos e futuros, e
proposições recebiam a data da sincronização em vez da de apresentação. Aqui o feed é
derivado do que está no banco, de forma idempotente:

- proposições: um item por autoria na legislatura, datado pela apresentação (o feed é uma
  linha do tempo: as mais antigas ficam mais abaixo; são ~50 mil itens, custo baixo);
- agenda: um item por evento de FEED_MAX_AGE_DAYS dias atrás até AGENDA_DAYS_AHEAD à frente
  (compromissos futuros aparecem no topo do feed);
- itens existentes têm a data e o texto corrigidos; os sem origem (ou proposição sem data
  conhecida) são removidos.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import AgendaEvent, AuthorRole, Bill, BillAuthor, FeedEvent, FeedType
from app.services.stats import STATS_BILL_TYPES, legislature_start_year
from ingestion.jobs.common import tracked

Key = tuple[uuid.UUID, uuid.UUID]  # (politician_id, ref_id)


def _bill_label(b: Bill) -> str:
    return f"{b.type} {b.number}/{b.year}" if b.number and b.year else b.type


async def _desired_bills(db, since: datetime) -> dict[Key, tuple[datetime, dict]]:
    rows = await db.execute(
        select(BillAuthor.politician_id, Bill)
        .join(Bill, Bill.id == BillAuthor.bill_id)
        .where(
            BillAuthor.role == AuthorRole.autor,
            Bill.type.in_(STATS_BILL_TYPES),
            Bill.presented_at >= since,
        )
    )
    return {
        (pid, b.id): (
            b.presented_at,
            {"title": (b.official_summary or "")[:300], "bill": _bill_label(b), "url": b.url},
        )
        for pid, b in rows.all()
    }


async def _desired_agenda(db, since: datetime, until: datetime) -> dict[Key, tuple[datetime, dict]]:
    rows = await db.execute(
        select(AgendaEvent).where(
            AgendaEvent.politician_id.is_not(None),
            AgendaEvent.starts_at >= since,
            AgendaEvent.starts_at < until,
        )
    )
    return {
        (e.politician_id, e.id): (
            e.starts_at,
            {"title": e.title[:300], "organ": e.organ, "starts_at": e.starts_at.isoformat()},
        )
        for e in rows.scalars()
    }


async def _bill_dates(db, ids: list[uuid.UUID]) -> dict[uuid.UUID, datetime | None]:
    out: dict[uuid.UUID, datetime | None] = {}
    for i in range(0, len(ids), 500):
        rows = await db.execute(
            select(Bill.id, Bill.presented_at).where(Bill.id.in_(ids[i : i + 500]))
        )
        out.update(rows.all())
    return out


async def _agenda_dates(db, ids: list[uuid.UUID]) -> dict[uuid.UUID, datetime]:
    out: dict[uuid.UUID, datetime] = {}
    for i in range(0, len(ids), 500):
        rows = await db.execute(
            select(AgendaEvent.id, AgendaEvent.starts_at).where(
                AgendaEvent.id.in_(ids[i : i + 500])
            )
        )
        out.update(rows.all())
    return out


async def reconcile(db, type_: FeedType, desired: dict[Key, tuple[datetime, dict]]) -> dict:
    """Cria o que falta, corrige data/texto do que existe e remove o que não tem origem."""
    existing = list((await db.execute(select(FeedEvent).where(FeedEvent.type == type_))).scalars())
    refs = list({e.ref_id for e in existing})
    if type_ == FeedType.bill:
        true_dates = await _bill_dates(db, refs)
    else:
        true_dates = await _agenda_dates(db, refs)

    created = updated = removed = 0
    seen: set[Key] = set()
    stale: list[int] = []
    for e in existing:
        key = (e.politician_id, e.ref_id)
        when = true_dates.get(e.ref_id)
        if key in seen or when is None or key not in desired:
            # duplicado, origem apagada, proposição sem data conhecida ou que deixou de contar
            # (requerimento, fora da legislatura, agenda fora da janela)
            stale.append(e.id)
            continue
        seen.add(key)
        payload = desired[key][1]
        if e.occurred_at != when or e.payload != payload:
            e.occurred_at, e.payload = when, payload
            updated += 1
    for i in range(0, len(stale), 500):
        await db.execute(delete(FeedEvent).where(FeedEvent.id.in_(stale[i : i + 500])))
    removed = len(stale)

    for key, (when, payload) in desired.items():
        if key in seen:
            continue
        pid, ref = key
        db.add(FeedEvent(politician_id=pid, type=type_, ref_id=ref, occurred_at=when,
                         payload=payload))  # fmt: skip
        created += 1
    await db.commit()
    return {"created": created, "updated": updated, "removed": removed}


async def run() -> None:
    s = get_settings()
    now = datetime.now(UTC)
    since = now - timedelta(days=s.feed_max_age_days)
    leg_start = datetime(legislature_start_year(s.legislature), 2, 1, tzinfo=UTC)
    async with tracked("sync_feed", "db") as run_, SessionLocal() as db:
        bills = await reconcile(db, FeedType.bill, await _desired_bills(db, leg_start))
        agenda_until = now + timedelta(days=s.agenda_days_ahead)
        agenda = await reconcile(
            db, FeedType.agenda, await _desired_agenda(db, since, agenda_until)
        )
        run_.items += sum(bills.values()) + sum(agenda.values())

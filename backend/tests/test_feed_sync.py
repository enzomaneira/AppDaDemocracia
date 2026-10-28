from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models import (
    AgendaEvent,
    AuthorRole,
    Bill,
    BillAuthor,
    FeedEvent,
    FeedType,
    House,
)
from ingestion.jobs import sync_feed
from tests.conftest import auth, register

NOW = datetime.now(UTC)


async def _bill(db, seed, ext, presented_at, tipo="PL"):
    b = Bill(house=House.camara, external_id=ext, type=tipo, number=int(ext[1:]), year=2026,
             official_summary=f"Ementa {ext}", presented_at=presented_at)  # fmt: skip
    db.add(b)
    await db.flush()
    db.add(BillAuthor(bill_id=b.id, politician_id=seed["a"].id, role=AuthorRole.autor))
    return b


async def _events(db, type_):
    rows = await db.execute(select(FeedEvent).where(FeedEvent.type == type_))
    return {e.ref_id: e for e in rows.scalars()}


async def test_bills_feed_uses_presentation_date_and_window(db, seed):
    recent = await _bill(db, seed, "n1", NOW - timedelta(days=3))
    old = await _bill(db, seed, "n2", NOW - timedelta(days=200))
    before_leg = await _bill(db, seed, "n7", datetime(2022, 12, 1, tzinfo=UTC))  # outra legislatura
    undated = await _bill(db, seed, "n3", None)
    req = await _bill(db, seed, "n4", NOW - timedelta(days=1), tipo="REQ")
    # item antigo com a data errada (data da sincronização), como os que estavam em produção
    db.add(FeedEvent(politician_id=seed["a"].id, type=FeedType.bill, ref_id=old.id,
                     occurred_at=NOW, payload={}))  # fmt: skip
    db.add(FeedEvent(politician_id=seed["a"].id, type=FeedType.bill, ref_id=undated.id,
                     occurred_at=NOW, payload={}))  # fmt: skip
    await db.commit()

    await sync_feed.run()
    ev = await _events(db, FeedType.bill)
    assert ev[recent.id].occurred_at == recent.presented_at
    assert ev[recent.id].payload["bill"] == "PL 1/2026"
    assert ev[old.id].occurred_at == old.presented_at  # corrigido para a data real: afunda no feed
    assert undated.id not in ev  # sem data conhecida: removido
    assert req.id not in ev  # requerimento não é proposição apresentada
    assert before_leg.id not in ev


async def test_agenda_feed_covers_window_including_existing_and_future(db, seed):
    a = seed["a"]
    events = {
        "futuro": NOW + timedelta(days=2),
        "passado": NOW - timedelta(days=5),
        "longe": NOW + timedelta(days=40),  # fora da janela
        "antigo": NOW - timedelta(days=90),  # fora da janela
    }
    ids = {}
    for name, when in events.items():
        e = AgendaEvent(house=House.camara, external_id=name, politician_id=a.id,
                        title=f"Reunião {name}", organ="CCJC", starts_at=when)  # fmt: skip
        db.add(e)
        await db.flush()
        ids[name] = e.id
    await db.commit()

    await sync_feed.run()
    ev = await _events(db, FeedType.agenda)
    assert set(ev) == {ids["futuro"], ids["passado"]}
    assert ev[ids["futuro"]].occurred_at == events["futuro"]
    assert ev[ids["futuro"]].payload["organ"] == "CCJC"


async def test_reconcile_is_idempotent_and_follows_changes(db, seed):
    b = await _bill(db, seed, "n5", NOW - timedelta(days=2))
    e = AgendaEvent(house=House.camara, external_id="r1", politician_id=seed["a"].id,
                    title="Audiência", starts_at=NOW + timedelta(days=1))  # fmt: skip
    db.add(e)
    await db.commit()
    await sync_feed.run()
    await sync_feed.run()  # de novo: não duplica
    assert len(await _events(db, FeedType.bill)) == 1
    assert len(await _events(db, FeedType.agenda)) == 1

    # evento remarcado: o item acompanha a nova data
    e.starts_at = NOW + timedelta(days=3)
    await db.commit()
    await sync_feed.run()
    ag = await _events(db, FeedType.agenda)
    assert ag[e.id].occurred_at == e.starts_at
    assert b.id in await _events(db, FeedType.bill)


async def test_followed_feed_shows_bills_and_agenda(client, db, seed):
    await _bill(db, seed, "n6", NOW - timedelta(days=1))
    db.add(
        AgendaEvent(
            house=House.camara,
            external_id="r2",
            politician_id=seed["a"].id,
            title="Reunião deliberativa",
            starts_at=NOW + timedelta(days=1),
        )
    )
    await db.commit()
    await sync_feed.run()

    h = auth(await register(client))
    await client.put(f"/api/v1/me/follows/{seed['a'].id}", headers=h)
    types = [i["type"] for i in (await client.get("/api/v1/me/feed", headers=h)).json()["items"]]
    assert {"bill", "agenda"} <= set(types)
    assert types[0] == "agenda"  # compromisso futuro no topo
    only = (await client.get("/api/v1/me/feed", params={"type": "bill"}, headers=h)).json()
    assert [i["payload"]["bill"] for i in only["items"]] == ["PL 6/2026"]

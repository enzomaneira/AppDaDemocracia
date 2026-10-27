from datetime import UTC, datetime

from app.api.v1.compare import agreement_rate
from app.models import House, Vote, VoteChoice, VoteRecord
from app.services.stats import compute_all, parse_period

AB = {"a": "ana-souza-sp", "b": "bruno-lima-rj"}


def test_agreement_rate():
    assert agreement_rate(10, 2) == 80.0
    assert agreement_rate(3, 3) == 0.0
    assert agreement_rate(0, 0) is None


async def _add_vote(db, seed, ext, when, choice_a, choice_b):
    v = Vote(house=House.camara, external_id=ext, voted_at=when, description=f"Votação {ext}")
    db.add(v)
    await db.flush()
    db.add(VoteRecord(vote_id=v.id, politician_id=seed["a"].id, choice=VoteChoice(choice_a)))
    db.add(VoteRecord(vote_id=v.id, politician_id=seed["b"].id, choice=VoteChoice(choice_b)))
    await db.commit()
    return v


async def test_compare_summary_side_by_side(client, db, seed):
    # seed: v1 (mar/2026) Ana sim × Bruno não. Mais 3: duas iguais e uma com ausência.
    await _add_vote(db, seed, "v2", datetime(2026, 4, 1, tzinfo=UTC), "sim", "sim")
    await _add_vote(db, seed, "v3", datetime(2026, 4, 2, tzinfo=UTC), "nao", "nao")
    await _add_vote(db, seed, "v4", datetime(2026, 4, 3, tzinfo=UTC), "sim", "ausente")
    await compute_all(db, parse_period("2026", 57))

    body = (await client.get("/api/v1/compare", params={**AB, "period": "2026"})).json()
    assert body["a"]["slug"] == "ana-souza-sp" and body["b"]["slug"] == "bruno-lima-rj"
    assert body["same_house"] is True
    # ausência não entra na comparação: 3 em comum, 1 divergente
    assert (body["common_votes"], body["divergent_votes"]) == (3, 1)
    assert body["agreement_rate"] == 66.7
    assert body["stats_a"]["attendance_rate"]["value"] == 75.0
    assert body["stats_b"]["attendance_rate"]["value"] == 50.0


async def test_compare_votes_list_and_divergent_filter(client, db, seed):
    await _add_vote(db, seed, "v2", datetime(2026, 4, 1, tzinfo=UTC), "sim", "sim")
    r = (await client.get("/api/v1/compare/votes", params=AB)).json()
    assert [(i["choice_a"], i["choice_b"], i["agree"]) for i in r["items"]] == [
        ("sim", "sim", True),  # mais recente primeiro
        ("sim", "nao", False),
    ]
    only = (await client.get("/api/v1/compare/votes", params={**AB, "divergent": True})).json()
    assert [i["vote"]["bill"]["type"] for i in only["items"]] == ["PL"]


async def test_compare_votes_pagination(client, db, seed):
    for d in range(1, 6):
        await _add_vote(db, seed, f"p{d}", datetime(2026, 5, d, tzinfo=UTC), "sim", "sim")
    page1 = (await client.get("/api/v1/compare/votes", params={**AB, "limit": 4})).json()
    assert len(page1["items"]) == 4 and page1["next_cursor"]
    page2 = (
        await client.get(
            "/api/v1/compare/votes", params={**AB, "limit": 4, "cursor": page1["next_cursor"]}
        )
    ).json()
    assert len(page2["items"]) == 2 and page2["next_cursor"] is None


async def test_compare_period_filter(client, seed):
    body = (await client.get("/api/v1/compare", params={**AB, "period": "2025"})).json()
    assert body["common_votes"] == 0 and body["agreement_rate"] is None


async def test_compare_across_houses(client, seed):
    body = (
        await client.get("/api/v1/compare", params={"a": "ana-souza-sp", "b": "carla-dias-mg"})
    ).json()
    assert body["same_house"] is False and body["common_votes"] == 0


async def test_compare_errors(client, seed):
    same = await client.get("/api/v1/compare", params={"a": "ana-souza-sp", "b": "ana-souza-sp"})
    assert same.status_code == 400
    missing = await client.get("/api/v1/compare", params={"a": "ana-souza-sp", "b": "nao-existe"})
    assert missing.status_code == 404
    bad = await client.get("/api/v1/compare", params={**AB, "period": "xyz"})
    assert bad.status_code == 400

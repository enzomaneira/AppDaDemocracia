from datetime import UTC, datetime

import pytest

from app.services.feed import decode_cursor, encode_cursor
from app.services.stats import compute_all, parse_period
from tests.conftest import auth, register


def test_cursor_roundtrip():
    t = datetime(2026, 1, 2, 3, 4, tzinfo=UTC)
    assert decode_cursor(encode_cursor(t, 42)) == (t, "42")
    with pytest.raises(ValueError):
        decode_cursor("lixo")


async def test_health(client):
    r = await client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_register_login_refresh(client):
    tokens = await register(client)
    me = await client.get("/api/v1/me", headers=auth(tokens))
    assert me.json()["email"] == "eleitor@example.com"

    dup = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "ELEITOR@example.com",
            "name": "x",
            "password": "12345678",
            "accept_terms": True,
        },
    )
    assert dup.status_code == 409

    bad = await client.post(
        "/api/v1/auth/login", json={"email": "eleitor@example.com", "password": "errada123"}
    )
    assert bad.status_code == 401
    ok = await client.post(
        "/api/v1/auth/login", json={"email": "eleitor@example.com", "password": "senha-forte-123"}
    )
    assert ok.status_code == 200

    r1 = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r1.status_code == 200
    # rotação: o mesmo refresh token não pode ser usado duas vezes
    r2 = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r2.status_code == 401


async def test_register_requires_terms(client):
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": "a@b.com", "name": "x", "password": "12345678", "accept_terms": False},
    )
    assert r.status_code == 400


async def test_search_filters(client, seed):
    r = await client.get("/api/v1/politicians", params={"uf": "SP"})
    assert [p["slug"] for p in r.json()["items"]] == ["ana-souza-sp"]
    r = await client.get("/api/v1/politicians", params={"house": "senado"})
    assert [p["slug"] for p in r.json()["items"]] == ["carla-dias-mg"]
    r = await client.get("/api/v1/politicians", params={"q": "bruno", "party": "pb"})
    assert [p["slug"] for p in r.json()["items"]] == ["bruno-lima-rj"]


async def test_search_pagination(client, seed):
    r = await client.get("/api/v1/politicians", params={"limit": 2})
    body = r.json()
    assert len(body["items"]) == 2 and body["next_cursor"]
    r2 = await client.get("/api/v1/politicians", params={"limit": 2, "cursor": body["next_cursor"]})
    assert len(r2.json()["items"]) == 1


async def test_profile_stats_votes(client, db, seed):
    await compute_all(db, parse_period("2026", 57))
    r = await client.get("/api/v1/politicians/ana-souza-sp")
    assert r.status_code == 200
    assert r.json()["official_url"].endswith("/deputados/1")

    s = (
        await client.get("/api/v1/politicians/ana-souza-sp/stats", params={"period": "2026"})
    ).json()
    assert s["attendance_rate"] == {"value": 75.0, "house_avg": 62.5}
    assert s["sessions_justified"] == 1 and s["sessions_absent"] == 0

    v = (await client.get("/api/v1/politicians/bruno-lima-rj/votes")).json()["items"][0]
    assert v["choice"] == "nao" and v["with_party"] is False
    assert v["vote"]["bill"]["type"] == "PL"

    e = (
        await client.get("/api/v1/politicians/ana-souza-sp/expenses", params={"year": 2026})
    ).json()
    assert float(e["total"]) == 1000.5

    n = (await client.get("/api/v1/politicians/ana-souza-sp/news")).json()
    assert n["items"][0]["source_name"] == "Exemplo"

    assert (await client.get("/api/v1/politicians/nao-existe")).status_code == 404


async def test_follow_feed_and_vote_detail(client, seed):
    tokens = await register(client)
    h = auth(tokens)
    ana = seed["a"]
    assert (await client.get("/api/v1/me/feed", headers=h)).json()["items"] == []

    r = await client.put(f"/api/v1/me/follows/{ana.id}", headers=h, json={"notify_news": False})
    assert r.status_code == 200
    follows = (await client.get("/api/v1/me/follows", headers=h)).json()
    assert follows[0]["politician"]["slug"] == "ana-souza-sp"
    assert follows[0]["notify_news"] is False

    feed = (await client.get("/api/v1/me/feed", headers=h)).json()["items"]
    assert len(feed) == 1 and feed[0]["payload"]["choice"] == "sim"

    detail = (await client.get(f"/api/v1/votes/{seed['vote'].id}", headers=h)).json()
    assert detail["records"][0]["is_followed"] is True
    assert detail["records"][0]["politician"]["slug"] == "ana-souza-sp"

    news = (await client.get("/api/v1/news", headers=h)).json()
    assert len(news["items"]) == 1

    prof = (await client.get("/api/v1/politicians/ana-souza-sp", headers=h)).json()
    assert prof["is_following"] is True

    await client.delete(f"/api/v1/me/follows/{ana.id}", headers=h)
    assert (await client.get("/api/v1/me/follows", headers=h)).json() == []


async def test_follow_list_is_private(client, seed):
    assert (await client.get("/api/v1/me/follows")).status_code == 401
    assert (await client.get("/api/v1/me/feed")).status_code == 401


async def test_compare(client, db, seed):
    await compute_all(db, parse_period("2026", 57))
    r = await client.get("/api/v1/compare", params={"a": "ana-souza-sp", "b": "bruno-lima-rj"})
    body = r.json()
    assert body["common_votes"] == 1 and body["divergent_votes"] == 1


async def test_lgpd_export_and_delete(client, seed):
    tokens = await register(client)
    h = auth(tokens)
    await client.put(f"/api/v1/me/follows/{seed['a'].id}", headers=h)
    export = (await client.get("/api/v1/me/export", headers=h)).json()
    assert export["user"]["email"] == "eleitor@example.com"
    assert len(export["follows"]) == 1

    assert (await client.delete("/api/v1/me", headers=h)).status_code == 204
    assert (await client.get("/api/v1/me", headers=h)).status_code == 401
    # e-mail liberado para novo cadastro
    await register(client)


async def test_admin_requires_role(client):
    tokens = await register(client)
    r = await client.get("/api/v1/admin/ingestion-runs", headers=auth(tokens))
    assert r.status_code == 403

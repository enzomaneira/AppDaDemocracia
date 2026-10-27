from app.models import AuthorRole, Bill, BillAuthor, House

URL = "/api/v1/politicians/ana-souza-sp/bills"


async def _bill(db, seed, ext, tipo, number, year, ementa, who="a"):
    b = Bill(house=House.camara, external_id=ext, type=tipo, number=number, year=year,
             official_summary=ementa, url=f"https://exemplo.gov.br/{ext}")  # fmt: skip
    db.add(b)
    await db.flush()
    db.add(BillAuthor(bill_id=b.id, politician_id=seed[who].id, role=AuthorRole.autor))
    await db.commit()


async def test_lists_only_projects_newest_first(client, db, seed):
    # seed: PL 10/2026 "Dispõe sobre transparência." de Ana
    await _bill(db, seed, "b2", "PEC", 3, 2024, "Altera a Constituição para a saúde")
    await _bill(db, seed, "b3", "REQ", 99, 2026, "Requer informações")  # não é projeto
    await _bill(db, seed, "b4", "PL", 7, 2026, "Institui o programa de educação")
    await _bill(db, seed, "b5", "PL", 1, 2025, "Projeto do Bruno", who="b")  # de outro

    body = (await client.get(URL)).json()
    assert [f"{i['type']} {i['number']}/{i['year']}" for i in body["items"]] == [
        "PL 10/2026",
        "PL 7/2026",
        "PEC 3/2024",
    ]
    assert body["total"] == 3 and body["by_type"] == {"PL": 2, "PEC": 1}
    assert body["items"][0]["url"]  # link para a ficha oficial


async def test_filters_by_type_and_search(client, db, seed):
    await _bill(db, seed, "b2", "PEC", 3, 2024, "Altera a Constituição para a saúde")
    await _bill(db, seed, "b4", "PL", 7, 2026, "Institui o programa de educação")

    pec = (await client.get(URL, params={"type": "pec"})).json()
    assert [i["type"] for i in pec["items"]] == ["PEC"] and pec["total"] == 1
    # os chips continuam mostrando todos os tipos
    assert pec["by_type"] == {"PL": 2, "PEC": 1}

    texto = (await client.get(URL, params={"q": "educação"})).json()
    assert [i["number"] for i in texto["items"]] == [7]

    for q, esperado in [("7/2026", [7]), ("PL 10", [10]), ("3", [3]), ("10/2025", [])]:
        r = (await client.get(URL, params={"q": q})).json()
        assert [i["number"] for i in r["items"]] == esperado, q


async def test_pagination_and_errors(client, db, seed):
    for n in range(1, 6):
        await _bill(db, seed, f"p{n}", "PL", 100 + n, 2025, f"Projeto {n}")
    p1 = (await client.get(URL, params={"limit": 4})).json()
    assert len(p1["items"]) == 4 and p1["next_cursor"] and p1["total"] == 6
    p2 = (await client.get(URL, params={"limit": 4, "cursor": p1["next_cursor"]})).json()
    assert len(p2["items"]) == 2 and p2["next_cursor"] is None
    seen = {i["id"] for i in p1["items"]} | {i["id"] for i in p2["items"]}
    assert len(seen) == 6  # sem repetir nem pular

    assert (await client.get(URL, params={"type": "REQ"})).status_code == 400
    assert (await client.get(URL, params={"cursor": "lixo"})).status_code == 400
    assert (await client.get("/api/v1/politicians/nao-existe/bills")).status_code == 404

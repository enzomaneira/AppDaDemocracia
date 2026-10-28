import pytest

from app.core.config import get_settings
from app.services.survey import QUESTIONS, SurveyError, clean_answers, summarize
from tests.conftest import auth, register

URL = "/api/v1/waitlist"
OK = {
    "frequencia": "eleicao",
    "barreiras": ["linguagem", "tempo"],
    "temas": ["saude", "educacao", "transparencia"],
    "aberta": "  Explicar  em linguagem simples  ",
}


def body(email="eleitora@example.com", **kw):
    return {"email": email, "accept_privacy": True, "answers": OK, **kw}


def test_survey_definition_is_consistent():
    ids = [q["id"] for q in QUESTIONS]
    assert len(ids) == len(set(ids))
    for q in QUESTIONS:
        opts = [o for o, _ in q.get("options", [])]
        assert len(opts) == len(set(opts)), q["id"]
    # LGPD: nada de partido, voto ou posição política
    text = " ".join(q["text"].lower() for q in QUESTIONS)
    assert "partido" not in text and "votou em" not in text


def test_clean_answers_validates_against_definition():
    out = clean_answers(OK)
    assert out["frequencia"] == "eleicao"
    assert out["aberta"] == "Explicar em linguagem simples"  # espaços normalizados
    assert clean_answers({"temas": ["saude", "saude"]}) == {"temas": ["saude"]}
    assert clean_answers({"frequencia": "", "temas": []}) == {}  # tudo é opcional
    for bad in (
        {"inexistente": "x"},
        {"frequencia": "talvez"},
        {"frequencia": ["eleicao", "diario"]},  # pergunta de escolha única
        {"temas": ["saude", "educacao", "agro", "moradia"]},  # máximo 3
        {"aberta": 123},
    ):
        with pytest.raises(SurveyError):
            clean_answers(bad)
    assert len(clean_answers({"aberta": "x" * 900})["aberta"]) == 500


def test_summarize_counts_options():
    s = {q["id"]: q for q in summarize([{"temas": ["saude", "educacao"]}, {"temas": ["saude"]}])}
    counts = {o["id"]: o["count"] for o in s["temas"]["options"]}
    assert counts["saude"] == 2 and counts["educacao"] == 1 and s["temas"]["answered"] == 2
    assert "aberta" not in s  # aberta não entra nas barras


async def test_join_and_position(client):
    r1 = await client.post(URL, json=body(uf="sp", age_range="25-34", source="instagram"))
    assert r1.status_code == 200, r1.text
    assert r1.json() == {"position": 1, "total": 1, "updated": False}
    r2 = await client.post(URL, json=body(email="outro@example.com"))
    assert r2.json()["position"] == 2 and r2.json()["total"] == 2
    assert (await client.get(f"{URL}/count")).json() == {"total": 2}


async def test_same_email_updates_without_duplicating(client):
    await client.post(URL, json=body(answers={"temas": ["saude"]}))
    r = await client.post(URL, json=body(email="ELEITORA@example.com", answers={"voz": "sim"}))
    assert r.json()["updated"] is True and r.json()["total"] == 1


async def test_requires_privacy_and_valid_fields(client):
    assert (await client.post(URL, json=body(accept_privacy=False))).status_code == 400
    assert (await client.post(URL, json=body(uf="XX"))).status_code == 400
    assert (await client.post(URL, json=body(age_range="10-12"))).status_code == 400
    assert (await client.post(URL, json=body(answers={"temas": ["xyz"]}))).status_code == 400
    assert (await client.post(URL, json=body(email="nao-e-email"))).status_code == 422


async def test_survey_endpoint(client):
    s = (await client.get(f"{URL}/survey")).json()
    assert [q["id"] for q in s["questions"]] == [q["id"] for q in QUESTIONS]
    assert s["age_ranges"][0]["id"] == "16-24"


async def test_admin_results_are_restricted(client, monkeypatch):
    await client.post(URL, json=body(uf="SP"))
    h = auth(await register(client, email="enzo@example.com"))
    assert (await client.get("/api/v1/admin/waitlist/summary", headers=h)).status_code == 403
    assert (await client.get("/api/v1/me", headers=h)).json()["is_admin"] is False

    monkeypatch.setattr(get_settings(), "admin_emails", "outra@x.com, Enzo@Example.com")
    assert (await client.get("/api/v1/me", headers=h)).json()["is_admin"] is True
    s = (await client.get("/api/v1/admin/waitlist/summary", headers=h)).json()
    assert s["total"] == 1 and s["by_uf"] == {"SP": 1}
    assert s["open_answers"][0]["text"] == "Explicar em linguagem simples"
    csv = await client.get("/api/v1/admin/waitlist/export.csv", headers=h)
    assert csv.status_code == 200 and "eleitora@example.com" in csv.text
    assert csv.text.startswith("﻿inscrito_em,email")

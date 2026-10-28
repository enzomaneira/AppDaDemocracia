from datetime import UTC, datetime, timedelta

import pytest

from app.core.config import get_settings
from app.services.survey import (
    QUESTIONS,
    REMIND_AFTER_DAYS,
    SurveyError,
    clean_answers,
    prompt_state,
    summarize,
)
from tests.conftest import auth, register

ME = "/api/v1/me/survey"
OK = {
    "frequencia": "eleicao",
    "barreiras": ["linguagem", "tempo"],
    "temas": ["saude", "educacao", "transparencia"],
    "idade": "25-34",
    "aberta": "  Explicar  em linguagem simples  ",
}
NOW = datetime(2026, 11, 1, 12, tzinfo=UTC)


def test_survey_definition_is_consistent():
    ids = [q["id"] for q in QUESTIONS]
    assert len(ids) == len(set(ids)) and "idade" in ids
    for q in QUESTIONS:
        opts = [o for o, _ in q.get("options", [])]
        assert len(opts) == len(set(opts)), q["id"]
    # LGPD: nada de partido, voto ou posição política
    text = " ".join(q["text"].lower() for q in QUESTIONS)
    assert "partido" not in text and "votou em" not in text


def test_clean_answers_validates_against_definition():
    out = clean_answers(OK)
    assert out["frequencia"] == "eleicao" and out["idade"] == "25-34"
    assert out["aberta"] == "Explicar em linguagem simples"
    assert clean_answers({"temas": ["saude", "saude"]}) == {"temas": ["saude"]}
    assert clean_answers({"frequencia": "", "temas": []}) == {}
    for bad in (
        {"inexistente": "x"},
        {"frequencia": "talvez"},
        {"frequencia": ["eleicao", "diario"]},
        {"temas": ["saude", "educacao", "agro", "moradia"]},
        {"aberta": 123},
    ):
        with pytest.raises(SurveyError):
            clean_answers(bad)


def test_summarize_counts_options():
    s = {q["id"]: q for q in summarize([{"temas": ["saude", "educacao"]}, {"temas": ["saude"]}])}
    counts = {o["id"]: o["count"] for o in s["temas"]["options"]}
    assert counts["saude"] == 2 and counts["educacao"] == 1 and s["temas"]["answered"] == 2
    assert "aberta" not in s


def test_prompt_state_invites_at_most_twice():
    d = timedelta(days=1)
    assert prompt_state(False, None, None, None, NOW) == {"prompt": True, "remind": False}
    assert prompt_state(True, NOW, None, None, NOW) == {"prompt": False, "remind": False}
    # dispensou: nada até passarem os dias; depois um lembrete; depois nunca mais
    assert prompt_state(True, None, NOW - d, None, NOW) == {"prompt": False, "remind": False}
    late = NOW - timedelta(days=REMIND_AFTER_DAYS)
    assert prompt_state(True, None, late, None, NOW) == {"prompt": False, "remind": True}
    assert prompt_state(True, None, late, NOW, NOW) == {"prompt": False, "remind": False}


async def test_new_account_is_invited_and_can_answer_or_edit(client):
    h = auth(await register(client))
    first = (await client.get(ME, headers=h)).json()
    assert first == {"answers": {}, "completed_at": None, "prompt": True, "remind": False}

    r = await client.put(ME, headers=h, json={"answers": OK})
    assert r.status_code == 200 and r.json()["prompt"] is False
    assert r.json()["answers"]["temas"] == ["saude", "educacao", "transparencia"]
    # edição substitui as respostas
    r = await client.put(ME, headers=h, json={"answers": {"voz": "sim"}})
    assert r.json()["answers"] == {"voz": "sim"}
    bad = await client.put(ME, headers=h, json={"answers": {"temas": ["xyz"]}})
    assert bad.status_code == 400


async def test_dismiss_then_single_reminder(client, db):
    from app.models import SurveyResponse

    tokens = await register(client)
    h = auth(tokens)
    r = (await client.post(f"{ME}/dismiss", headers=h, json={})).json()
    assert r["prompt"] is False and r["remind"] is False
    # simula os dias passando
    me = (await client.get("/api/v1/me", headers=h)).json()
    import uuid

    row = await db.get(SurveyResponse, uuid.UUID(me["id"]))
    row.dismissed_at = datetime.now(UTC) - timedelta(days=REMIND_AFTER_DAYS + 1)
    await db.commit()
    assert (await client.get(ME, headers=h)).json()["remind"] is True
    r = (await client.post(f"{ME}/dismiss", headers=h, json={"reminder": True})).json()
    assert r["remind"] is False  # lembrete visto: não insiste mais


async def test_survey_requires_login(client):
    assert (await client.get(ME)).status_code == 401
    assert (await client.put(ME, json={"answers": {}})).status_code == 401
    assert (await client.get("/api/v1/survey")).status_code == 200  # definição é pública


async def test_lgpd_export_includes_and_delete_removes_answers(client, db):
    from sqlalchemy import func, select

    from app.models import SurveyResponse

    h = auth(await register(client))
    await client.put(ME, headers=h, json={"answers": OK})
    export = (await client.get("/api/v1/me/export", headers=h)).json()
    assert export["survey"]["frequencia"] == "eleicao"
    assert (await client.delete("/api/v1/me", headers=h)).status_code == 204
    count = (await db.execute(select(func.count()).select_from(SurveyResponse))).scalar()
    assert count == 0


async def test_admin_summary_rate_and_anonymous_csv(client, monkeypatch):
    a = auth(await register(client, email="a@example.com"))
    b = auth(await register(client, email="b@example.com"))
    await register(client, email="c@example.com")
    await client.put(ME, headers=a, json={"answers": OK})
    await client.post(f"{ME}/dismiss", headers=b, json={})

    admin = auth(await register(client, email="enzo@example.com"))
    assert (await client.get("/api/v1/admin/survey/summary", headers=admin)).status_code == 403
    monkeypatch.setattr(get_settings(), "admin_emails", "enzo@example.com")
    s = (await client.get("/api/v1/admin/survey/summary", headers=admin)).json()
    assert (s["users"], s["responses"], s["dismissed"]) == (4, 1, 1)
    assert s["response_rate"] == 25.0
    assert s["open_answers"][0]["text"] == "Explicar em linguagem simples"
    csv = (await client.get("/api/v1/admin/survey/export.csv", headers=admin)).text
    assert csv.startswith("﻿respondido_em,uf,")
    assert "a@example.com" not in csv and "@" not in csv  # anônimo

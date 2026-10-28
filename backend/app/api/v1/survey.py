"""Pesquisa opcional ligada à conta, e resultados agregados para o admin."""

import csv
import io
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.deps import DB, AdminUser, CurrentUser
from app.models import User
from app.models.survey import SurveyResponse
from app.services.survey import (
    QUESTIONS,
    SURVEY_VERSION,
    SurveyError,
    clean_answers,
    prompt_state,
    public_survey,
    summarize,
)

router = APIRouter(tags=["survey"])


class SurveyIn(BaseModel):
    answers: dict = Field(default_factory=dict)


class DismissIn(BaseModel):
    # true quando a pessoa fecha o lembrete (o segundo e último convite)
    reminder: bool = False


class MySurvey(BaseModel):
    answers: dict
    completed_at: datetime | None
    prompt: bool
    remind: bool


def _out(row: SurveyResponse | None) -> MySurvey:
    state = prompt_state(
        row is not None,
        row.completed_at if row else None,
        row.dismissed_at if row else None,
        row.reminded_at if row else None,
        datetime.now(UTC),
    )
    return MySurvey(
        answers=(row.answers or {}) if row else {},
        completed_at=row.completed_at if row else None,
        **state,
    )


@router.get("/survey")
async def survey() -> dict:
    """Definição das perguntas (pública)."""
    return public_survey()


@router.get("/me/survey", response_model=MySurvey)
async def my_survey(user: CurrentUser, db: DB) -> MySurvey:
    return _out(await db.get(SurveyResponse, user.id))


@router.put("/me/survey", response_model=MySurvey)
async def answer(body: SurveyIn, user: CurrentUser, db: DB) -> MySurvey:
    """Salva (ou edita) as respostas. Todas as perguntas são opcionais."""
    try:
        answers = clean_answers(body.answers)
    except SurveyError as e:
        raise HTTPException(400, str(e)) from e
    row = await db.get(SurveyResponse, user.id)
    if row is None:
        row = SurveyResponse(user_id=user.id)
        db.add(row)
    row.answers = answers
    row.survey_version = SURVEY_VERSION
    row.completed_at = datetime.now(UTC)
    await db.commit()
    return _out(row)


@router.post("/me/survey/dismiss", response_model=MySurvey)
async def dismiss(body: DismissIn, user: CurrentUser, db: DB) -> MySurvey:
    """ "Agora não": registra para não insistir (o lembrete aparece uma única vez)."""
    row = await db.get(SurveyResponse, user.id)
    if row is None:
        row = SurveyResponse(user_id=user.id, answers={})
        db.add(row)
    now = datetime.now(UTC)
    if body.reminder:
        row.reminded_at = now
    row.dismissed_at = row.dismissed_at or now
    await db.commit()
    return _out(row)


@router.get("/admin/survey/summary", tags=["admin"])
async def admin_summary(_: AdminUser, db: DB) -> dict:
    users = (
        await db.execute(select(func.count()).select_from(User).where(User.deleted_at.is_(None)))
    ).scalar_one()
    rows = (
        await db.execute(
            select(SurveyResponse, User.uf).join(User, User.id == SurveyResponse.user_id)
        )
    ).all()
    done = [(r, uf) for r, uf in rows if r.completed_at]
    dismissed = sum(1 for r, _ in rows if r.dismissed_at and not r.completed_at)
    by_uf: dict[str, int] = {}
    for _, uf in done:
        by_uf[uf or "—"] = by_uf.get(uf or "—", 0) + 1
    open_answers = [
        {"text": r.answers["aberta"], "uf": uf, "created_at": r.completed_at}
        for r, uf in sorted(done, key=lambda x: x[0].completed_at, reverse=True)
        if (r.answers or {}).get("aberta")
    ][:200]
    return {
        "users": users,
        "responses": len(done),
        "dismissed": dismissed,
        "response_rate": round(len(done) / users * 100, 1) if users else None,
        "questions": summarize([r.answers or {} for r, _ in done]),
        "by_uf": dict(sorted(by_uf.items(), key=lambda kv: -kv[1])),
        "open_answers": open_answers,
    }


@router.get("/admin/survey/export.csv", tags=["admin"])
async def admin_export(_: AdminUser, db: DB) -> StreamingResponse:
    """CSV anônimo: sem e-mail nem nome (as respostas são analisadas de forma agregada)."""
    rows = (
        await db.execute(
            select(SurveyResponse, User.uf)
            .join(User, User.id == SurveyResponse.user_id)
            .where(SurveyResponse.completed_at.is_not(None))
            .order_by(SurveyResponse.completed_at)
        )
    ).all()
    qids = [q["id"] for q in QUESTIONS]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["respondido_em", "uf", *qids])
    for r, uf in rows:
        a = r.answers or {}
        w.writerow(
            [r.completed_at.isoformat(), uf or "",
             *["; ".join(a[q]) if isinstance(a.get(q), list) else a.get(q, "") for q in qids]]
        )  # fmt: skip
    return StreamingResponse(
        iter(["﻿" + buf.getvalue()]),  # BOM: o Excel abre os acentos certos
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="pesquisa.csv"'},
    )

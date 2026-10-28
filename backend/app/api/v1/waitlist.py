"""Lista de espera com pesquisa (LP pública /lista) e resultados para o admin."""

import csv
import io
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select

from app.api.deps import DB, AdminUser
from app.core.config import get_settings
from app.core.ratelimit import limiter
from app.models.waitlist import WaitlistEntry
from app.services.survey import (
    AGE_RANGES,
    QUESTIONS,
    SURVEY_VERSION,
    SurveyError,
    clean_answers,
    public_survey,
    summarize,
)

router = APIRouter(tags=["waitlist"])
UFS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA",
    "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
}  # fmt: skip


class WaitlistIn(BaseModel):
    email: EmailStr
    name: str | None = Field(default=None, max_length=120)
    uf: str | None = Field(default=None, min_length=2, max_length=2)
    age_range: str | None = None
    answers: dict = Field(default_factory=dict)
    accept_privacy: bool
    source: str | None = Field(default=None, max_length=60)


class WaitlistOut(BaseModel):
    position: int
    total: int
    updated: bool


@router.get("/waitlist/survey")
async def survey() -> dict:
    return public_survey()


@router.get("/waitlist/count")
async def count(db: DB) -> dict:
    """Total de inscritos (prova social na LP). Não expõe nenhum dado pessoal."""
    total = (await db.execute(select(func.count()).select_from(WaitlistEntry))).scalar_one()
    return {"total": total}


@router.post("/waitlist", response_model=WaitlistOut)
@limiter.limit(get_settings().auth_rate_limit)
async def join(request: Request, body: WaitlistIn, db: DB) -> WaitlistOut:
    """Inscreve (ou atualiza as respostas de quem já está na lista, pelo e-mail)."""
    if not body.accept_privacy:
        raise HTTPException(400, "É preciso aceitar a política de privacidade")
    uf = body.uf.upper() if body.uf else None
    if uf and uf not in UFS:
        raise HTTPException(400, "UF inválida")
    if body.age_range and body.age_range not in {a for a, _ in AGE_RANGES}:
        raise HTTPException(400, "Faixa etária inválida")
    try:
        answers = clean_answers(body.answers)
    except SurveyError as e:
        raise HTTPException(400, str(e)) from e

    email = body.email.lower()
    entry = (
        await db.execute(select(WaitlistEntry).where(WaitlistEntry.email == email))
    ).scalar_one_or_none()
    updated = entry is not None
    if entry is None:
        entry = WaitlistEntry(email=email, consent_at=datetime.now(UTC))
        db.add(entry)
    entry.name = (body.name or "").strip() or entry.name
    entry.uf = uf or entry.uf
    entry.age_range = body.age_range or entry.age_range
    entry.answers = {**(entry.answers or {}), **answers}
    entry.survey_version = SURVEY_VERSION
    entry.source = entry.source or (body.source or None)
    await db.commit()
    await db.refresh(entry)

    earlier = select(func.count()).where(WaitlistEntry.created_at <= entry.created_at)
    position = (await db.execute(earlier.select_from(WaitlistEntry))).scalar_one()
    total = (await db.execute(select(func.count()).select_from(WaitlistEntry))).scalar_one()
    return WaitlistOut(position=position, total=total, updated=updated)


@router.get("/admin/waitlist/summary", tags=["admin"])
async def admin_summary(_: AdminUser, db: DB) -> dict:
    rows = (await db.execute(select(WaitlistEntry))).scalars().all()
    by_uf: dict[str, int] = {}
    by_age: dict[str, int] = {}
    by_source: dict[str, int] = {}
    for r in rows:
        by_uf[r.uf or "—"] = by_uf.get(r.uf or "—", 0) + 1
        by_age[r.age_range or "—"] = by_age.get(r.age_range or "—", 0) + 1
        by_source[r.source or "direto"] = by_source.get(r.source or "direto", 0) + 1
    open_answers = [
        {"text": r.answers["aberta"], "uf": r.uf, "created_at": r.created_at}
        for r in sorted(rows, key=lambda r: r.created_at, reverse=True)
        if (r.answers or {}).get("aberta")
    ][:200]
    return {
        "total": len(rows),
        "questions": summarize([r.answers or {} for r in rows]),
        "by_uf": dict(sorted(by_uf.items(), key=lambda kv: -kv[1])),
        "by_age": by_age,
        "by_source": dict(sorted(by_source.items(), key=lambda kv: -kv[1])),
        "open_answers": open_answers,
    }


@router.get("/admin/waitlist/export.csv", tags=["admin"])
async def admin_export(_: AdminUser, db: DB) -> StreamingResponse:
    rows = (
        (await db.execute(select(WaitlistEntry).order_by(WaitlistEntry.created_at))).scalars().all()
    )
    buf = io.StringIO()
    qids = [q["id"] for q in QUESTIONS]
    w = csv.writer(buf)
    w.writerow(["inscrito_em", "email", "nome", "uf", "faixa_etaria", "origem", *qids])
    for r in rows:
        a = r.answers or {}
        w.writerow(
            [r.created_at.isoformat(), r.email, r.name or "", r.uf or "", r.age_range or "",
             r.source or "", *["; ".join(a[q]) if isinstance(a.get(q), list) else a.get(q, "")
                                for q in qids]]
        )  # fmt: skip
    return StreamingResponse(
        iter(["﻿" + buf.getvalue()]),  # BOM: o Excel abre os acentos certos
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="lista-de-espera.csv"'},
    )

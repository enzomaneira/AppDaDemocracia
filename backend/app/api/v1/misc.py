"""Notícias dos seguidos, comparação, health check e rotas de admin."""

import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import case, func, select, text
from sqlalchemy.orm import aliased

from app.api.deps import DB, AdminUser, CurrentUser
from app.api.v1.me import followed_ids
from app.api.v1.politicians import get_by_slug, load_stats, news_page
from app.models import IngestionRun, NewsMention, VoteChoice, VoteRecord
from app.schemas import CompareOut, IngestionRunOut, NewsOut, Page
from app.services.presenters import politician_summary

router = APIRouter()


@router.get("/news", response_model=Page[NewsOut], tags=["news"])
async def news(
    user: CurrentUser,
    db: DB,
    politician: uuid.UUID | None = None,
    cursor: str | None = None,
    limit: int = Query(20, ge=1, le=100),
) -> Page[NewsOut]:
    ids = await followed_ids(db, user.id)
    if politician:
        ids = [i for i in ids if i == politician]
    try:
        return await news_page(db, ids, cursor, limit)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.get("/compare", response_model=CompareOut, tags=["compare"])
async def compare(db: DB, a: str, b: str, period: str | None = None) -> CompareOut:
    pa, pb = await get_by_slug(db, a), await get_by_slug(db, b)
    ra, rb = aliased(VoteRecord), aliased(VoteRecord)
    absent = VoteChoice.ausente
    q = (
        select(func.count(), func.sum(case((ra.choice != rb.choice, 1), else_=0)))
        .select_from(ra)
        .join(rb, rb.vote_id == ra.vote_id)
        .where(
            ra.politician_id == pa.id,
            rb.politician_id == pb.id,
            ra.choice != absent,
            rb.choice != absent,
        )
    )
    common, divergent = (await db.execute(q)).one()
    return CompareOut(
        a=politician_summary(pa),
        b=politician_summary(pb),
        stats_a=await load_stats(db, pa, period),
        stats_b=await load_stats(db, pb, period),
        common_votes=common or 0,
        divergent_votes=int(divergent or 0),
    )


@router.get("/health", tags=["ops"])
async def health(db: DB) -> dict:
    await db.execute(text("SELECT 1"))
    q = select(func.max(IngestionRun.finished_at)).where(IngestionRun.status == "ok")
    last = (await db.execute(q)).scalar()
    return {"status": "ok", "last_sync": last}


@router.get("/status", tags=["ops"])
async def data_status(db: DB) -> dict:
    """Quando cada fonte foi atualizada pela última vez — alimenta o "atualizado em" (RNF03)."""
    q = (
        select(IngestionRun.job, func.max(IngestionRun.finished_at))
        .where(IngestionRun.status == "ok")
        .group_by(IngestionRun.job)
    )
    return {"jobs": {job: ts for job, ts in (await db.execute(q)).all()}}


# --- Admin ----------------------------------------------------------------

admin = APIRouter(prefix="/admin", tags=["admin"])


@admin.get("/ingestion-runs", response_model=list[IngestionRunOut])
async def ingestion_runs(_: AdminUser, db: DB, limit: int = 50) -> list[IngestionRunOut]:
    q = select(IngestionRun).order_by(IngestionRun.started_at.desc()).limit(limit)
    return [IngestionRunOut.model_validate(r) for r in (await db.execute(q)).scalars()]


@admin.patch("/news-mentions/{article_id}/{politician_id}")
async def verify_mention(
    article_id: uuid.UUID, politician_id: uuid.UUID, _: AdminUser, db: DB, valid: bool = True
) -> dict:
    """Confirma (valid=true) ou remove (valid=false) um vínculo notícia-político."""
    m = await db.get(NewsMention, (article_id, politician_id))
    if not m:
        raise HTTPException(404, "Vínculo não encontrado")
    if valid:
        m.verified = True
    else:
        await db.delete(m)
    await db.commit()
    return {"ok": True}


router.include_router(admin)

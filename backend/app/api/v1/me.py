"""Rotas do usuário logado: conta (LGPD), seguidos e feed."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import delete, select

from app.api.deps import DB, CurrentUser
from app.models import FeedEvent, FeedType, Follow, Politician, RefreshToken
from app.schemas import FeedItem, FollowOut, FollowPrefs, Page, UserOut, UserUpdate
from app.services.feed import query_feed
from app.services.presenters import politician_summary

router = APIRouter(prefix="/me", tags=["me"])


@router.get("", response_model=UserOut)
async def get_me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.patch("", response_model=UserOut)
async def update_me(body: UserUpdate, user: CurrentUser, db: DB) -> UserOut:
    if body.name is not None:
        user.name = body.name.strip()
    if body.uf is not None:
        user.uf = body.uf.upper()
    await db.commit()
    return UserOut.model_validate(user)


@router.delete("", status_code=204)
async def delete_me(user: CurrentUser, db: DB) -> None:
    """Exclusão de conta (LGPD): apaga seguidos e tokens e anonimiza o registro."""
    await db.execute(delete(Follow).where(Follow.user_id == user.id))
    await db.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id))
    user.email = f"excluido-{user.id}@invalid"
    user.name = "Conta excluída"
    user.password_hash = None
    user.uf = None
    user.deleted_at = datetime.now(UTC)
    await db.commit()


@router.get("/export")
async def export_me(user: CurrentUser, db: DB) -> dict:
    """Exportação dos dados pessoais (LGPD)."""
    follows = await _follows(db, user.id)
    return {
        "exported_at": datetime.now(UTC).isoformat(),
        "user": UserOut.model_validate(user).model_dump(mode="json"),
        "follows": [f.model_dump(mode="json") for f in follows],
    }


async def _follows(db: DB, user_id: uuid.UUID) -> list[FollowOut]:
    q = (
        select(Follow, Politician)
        .join(Politician, Politician.id == Follow.politician_id)
        .where(Follow.user_id == user_id)
        .order_by(Politician.parliamentary_name)
    )
    return [
        FollowOut(
            politician=politician_summary(p),
            notify_votes=f.notify_votes,
            notify_agenda=f.notify_agenda,
            notify_news=f.notify_news,
            created_at=f.created_at,
        )
        for f, p in (await db.execute(q)).all()
    ]


@router.get("/follows", response_model=list[FollowOut])
async def list_follows(user: CurrentUser, db: DB) -> list[FollowOut]:
    return await _follows(db, user.id)


@router.put("/follows/{politician_id}", response_model=FollowPrefs)
async def follow(
    politician_id: uuid.UUID, user: CurrentUser, db: DB, prefs: FollowPrefs | None = None
) -> FollowPrefs:
    if not await db.get(Politician, politician_id):
        raise HTTPException(404, "Político não encontrado")
    prefs = prefs or FollowPrefs()
    f = await db.get(Follow, (user.id, politician_id))
    if f is None:
        f = Follow(user_id=user.id, politician_id=politician_id)
        db.add(f)
    f.notify_votes, f.notify_agenda, f.notify_news = (
        prefs.notify_votes,
        prefs.notify_agenda,
        prefs.notify_news,
    )
    await db.commit()
    return prefs


@router.delete("/follows/{politician_id}", status_code=204)
async def unfollow(politician_id: uuid.UUID, user: CurrentUser, db: DB) -> None:
    await db.execute(
        delete(Follow).where(Follow.user_id == user.id, Follow.politician_id == politician_id)
    )
    await db.commit()


async def followed_ids(db: DB, user_id: uuid.UUID) -> list[uuid.UUID]:
    q = select(Follow.politician_id).where(Follow.user_id == user_id)
    return list((await db.execute(q)).scalars())


@router.get("/feed", response_model=Page[FeedItem])
async def feed(
    user: CurrentUser,
    db: DB,
    type: FeedType | None = None,
    cursor: str | None = None,
    limit: int = Query(30, ge=1, le=100),
) -> Page[FeedItem]:
    ids = await followed_ids(db, user.id)
    try:
        events, next_cursor = await query_feed(db, ids, type, cursor, limit)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    pols = await _politicians_by_id(db, {e.politician_id for e in events})
    return Page(
        items=[_feed_item(e, pols[e.politician_id]) for e in events if e.politician_id in pols],
        next_cursor=next_cursor,
    )


async def _politicians_by_id(db: DB, ids: set[uuid.UUID]) -> dict[uuid.UUID, Politician]:
    if not ids:
        return {}
    rows = (await db.execute(select(Politician).where(Politician.id.in_(ids)))).scalars()
    return {p.id: p for p in rows}


def _feed_item(e: FeedEvent, p: Politician) -> FeedItem:
    return FeedItem(
        id=e.id,
        type=e.type.value,
        occurred_at=e.occurred_at,
        politician=politician_summary(p),
        payload={**e.payload, "ref_id": str(e.ref_id)},
    )

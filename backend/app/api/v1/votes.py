import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import DB, OptionalUser
from app.api.v1.me import followed_ids
from app.models import Politician, Vote, VoteRecord
from app.schemas import VoteDetail, VoteRecordOut
from app.services.presenters import politician_summary, vote_out

router = APIRouter(prefix="/votes", tags=["votes"])


@router.get("/{vote_id}", response_model=VoteDetail)
async def vote_detail(vote_id: uuid.UUID, db: DB, user: OptionalUser) -> VoteDetail:
    v = await db.get(Vote, vote_id)
    if not v:
        raise HTTPException(404, "Votação não encontrada")
    followed = set(await followed_ids(db, user.id)) if user else set()
    q = (
        select(VoteRecord, Politician)
        .join(Politician, Politician.id == VoteRecord.politician_id)
        .where(VoteRecord.vote_id == v.id)
        .order_by(Politician.parliamentary_name)
    )
    records = [
        VoteRecordOut(
            politician=politician_summary(p),
            choice=r.choice.value,
            party_orientation=r.party_orientation,
            is_followed=p.id in followed,
        )
        for r, p in (await db.execute(q)).all()
    ]
    # Seguidos em destaque, no topo da lista (RF11).
    records.sort(key=lambda r: not r.is_followed)
    return VoteDetail(**vote_out(v).model_dump(), records=records)

"""3 · Agenda dos próximos dias e presença nas sessões deliberativas encerradas (Câmara).

A presença no Senado e as ausências justificadas dependem de confirmar o formato
do registro de frequência nas fontes oficiais (questão em aberto do projeto).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import AgendaEvent, Attendance, AttendanceStatus, FeedType, House, Session
from app.services.feed import add_event
from ingestion.jobs.common import parse_dt, politician_index, tracked, upsert
from ingestion.sources.camara import CamaraSource, is_plenary_deliberative


async def sync_agenda_camara(api: CamaraSource) -> None:
    s = get_settings()
    today = datetime.now(UTC).date()
    start, end = (
        today - timedelta(days=s.sync_days_back),
        today + timedelta(days=s.agenda_days_ahead),
    )
    async with tracked("sync_agenda", "camara") as run, SessionLocal() as db:
        pols = {k: p for k, p in (await politician_index(db, House.camara)).items() if p.in_office}

        async def fetch(ext: str):
            return ext, [e async for e in api.deputado_eventos(ext, start, end)]

        results = await asyncio.gather(*(fetch(ext) for ext in pols))
        for ext, eventos in results:
            p = pols[ext]
            for e in eventos:
                starts = parse_dt(e.get("dataHoraInicio"))
                if not starts:
                    continue
                organ = ", ".join(o.get("sigla", "") for o in e.get("orgaos") or []) or None
                title = e.get("descricao") or e.get("descricaoTipo") or "Evento"
                ev, created = await upsert(
                    db,
                    AgendaEvent,
                    {"house": House.camara, "external_id": str(e["id"]), "politician_id": p.id},
                    {
                        "organ": organ,
                        "title": title,
                        "location": (e.get("localCamara") or {}).get("nome")
                        or e.get("localExterno"),
                        "starts_at": starts,
                        "ends_at": parse_dt(e.get("dataHoraFim")),
                        "status": e.get("situacao"),
                    },
                )
                if created and starts >= datetime.now(UTC):
                    await add_event(
                        db, p.id, FeedType.agenda, ev.id, starts,
                        {"title": title[:300], "organ": organ, "starts_at": starts.isoformat()},
                    )  # fmt: skip
                run.items += 1
        await db.commit()


async def sync_attendance_camara(api: CamaraSource) -> None:
    s = get_settings()
    today = datetime.now(UTC).date()
    start = today - timedelta(days=s.sync_days_back)
    async with tracked("sync_attendance", "camara") as run, SessionLocal() as db:
        pols = await politician_index(db, House.camara)
        in_office = {ext: p for ext, p in pols.items() if p.in_office}
        async for e in api.eventos(start, today):
            if not is_plenary_deliberative(e) or (e.get("situacao") or "") != "Encerrada":
                continue
            starts = parse_dt(e.get("dataHoraInicio"))
            sess, _ = await upsert(
                db,
                Session,
                {"house": House.camara, "external_id": str(e["id"])},
                {
                    "type": e.get("descricaoTipo"),
                    "is_deliberative": True,
                    "starts_at": starts,
                    "title": e.get("descricao"),
                },
            )
            present = {str(d["id"]) for d in await api.evento_deputados(e["id"])}
            existing = {
                a.politician_id: a
                for a in (
                    await db.execute(select(Attendance).where(Attendance.session_id == sess.id))
                ).scalars()
            }
            for ext, p in in_office.items():
                status = AttendanceStatus.presente if ext in present else AttendanceStatus.ausente
                a = existing.get(p.id)
                if a is None:
                    db.add(Attendance(session_id=sess.id, politician_id=p.id, status=status))
                elif a.status != AttendanceStatus.justificada:
                    a.status = status
                run.items += 1
            await db.commit()


async def run(camara: CamaraSource) -> None:
    await sync_agenda_camara(camara)
    await sync_attendance_camara(camara)

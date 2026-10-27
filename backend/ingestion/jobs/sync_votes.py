"""2 · Votações do período + votos nominais + orientação de bancada."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import UTC, date, datetime

from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models import (
    Attendance,
    AttendanceStatus,
    Bill,
    FeedType,
    House,
    Politician,
    Session,
    Vote,
    VoteChoice,
    VoteRecord,
)
from app.services.feed import add_event
from app.services.news_matching import normalize
from app.services.presenters import bill_url
from ingestion.jobs.common import (
    date_chunks,
    feed_worthy,
    in_exercise,
    parse_dt,
    politician_index,
    sync_start,
    tracked,
    upsert,
)
from ingestion.jobs.sync_bills import bill_label
from ingestion.sources import camara as cam
from ingestion.sources import senado as sen

log = logging.getLogger("ingestion.votes")
SENADO_RESULT = {"A": "Aprovada", "R": "Rejeitada"}


def senado_result(code: str | None) -> str | None:
    return SENADO_RESULT.get((code or "").upper(), code)


async def window(db, house: House) -> list[tuple[date, date]]:
    """Do último voto gravado da casa (ou do início da legislatura) até hoje, em blocos."""
    latest = (await db.execute(select(func.max(Vote.voted_at)).where(Vote.house == house))).scalar()
    return date_chunks(sync_start(latest), datetime.now(UTC).date())


def normalize_orientation(value: str | None) -> str | None:
    if not value:
        return None
    v = normalize(value)
    return {"nao": "nao", "sim": "sim", "abstencao": "abstencao", "obstrucao": "obstrucao"}.get(
        v, v
    )


def orientation_by_party(orientacoes: list[dict]) -> dict[str, str | None]:
    """Sigla do partido → orientação.

    A orientação pode vir do partido ("PL") ou de federação/bloco ("Fdr PT-PCdoB-PV");
    a do próprio partido (codTipoLideranca "P") tem precedência sobre a do bloco.
    """
    out: dict[str, str | None] = {}
    ordered = sorted(orientacoes, key=lambda o: o.get("codTipoLideranca") == "P")
    for o in ordered:
        sigla = (o.get("siglaPartidoBloco") or "").upper()
        value = normalize_orientation(o.get("orientacaoVoto"))
        tokens = [sigla] if o.get("codTipoLideranca") == "P" else re.split(r"[\s\-/]+", sigla)
        for t in tokens:
            if t and t not in {"FDR", "BLOCO", "GOVERNO", "MAIORIA", "MINORIA", "OPOSICAO"}:
                out[t] = value
    return out


def parse_identificacao(value: str | None) -> tuple[str | None, int | None, int | None]:
    """'PEC 81/2015' → ('PEC', 81, 2015)."""
    m = re.match(r"\s*([A-Za-z]+)\s+(\d+)/(\d{4})", value or "")
    if not m:
        return None, None, None
    return m.group(1).upper(), int(m.group(2)), int(m.group(3))


async def _save_vote(
    db,
    house: House,
    ext_id: str,
    voted_at: datetime,
    description: str | None,
    result: str | None,
    bill: Bill | None,
    choices: dict[str, tuple[str, str | None]],
    pols: dict[str, Politician],
    listed: set[str] | None = None,
) -> int:
    """Grava votação + votos nominais. `choices`: external_id → (escolha, orientação).

    `listed`: a lista completa de quem estava em exercício segundo a própria fonte (Senado:
    os 81 senadores aparecem em toda votação). Com ela, ninguém é preenchido como ausente,
    e registros de quem não está na lista (gravados por versões anteriores) são removidos.
    Sem ela (Câmara, que só lista quem votou), quem estava em exercício e não votou fica
    como ausente.
    """
    counts = {"sim": 0, "nao": 0, "abstencao": 0}
    for choice, _ in choices.values():
        if choice in counts:
            counts[choice] += 1
    vote, created = await upsert(
        db,
        Vote,
        {"house": house, "external_id": ext_id},
        {
            "voted_at": voted_at,
            "description": description,
            "result": result,
            "bill_id": bill.id if bill else None,
            "yes_count": counts["sim"],
            "no_count": counts["nao"],
            "abstention_count": counts["abstencao"],
        },
    )
    if listed is None:
        # Quem estava em exercício na data e não aparece na lista nominal fica como ausente.
        for ext, p in pols.items():
            if ext not in choices and in_exercise(p, voted_at):
                choices[ext] = ("ausente", None)

    existing = {
        r.politician_id: r
        for r in (
            await db.execute(select(VoteRecord).where(VoteRecord.vote_id == vote.id))
        ).scalars()
    }
    if listed is not None:
        keep = {pols[e].id for e in choices if e in pols}
        for pid, rec in list(existing.items()):
            if pid not in keep:
                await db.delete(rec)
                del existing[pid]
    title = (bill.official_summary if bill else None) or description or "Votação"
    to_feed = feed_worthy(voted_at)
    n = 0
    for ext, (choice, orientation) in choices.items():
        p = pols.get(ext)
        if not p:
            continue
        rec = existing.get(p.id)
        if rec is None:
            db.add(
                VoteRecord(
                    vote_id=vote.id,
                    politician_id=p.id,
                    choice=VoteChoice(choice),
                    party_orientation=orientation,
                )
            )
        if rec is None and to_feed:
            await add_event(
                db, p.id, FeedType.vote, vote.id, voted_at,
                {"title": title[:300], "choice": choice, "result": result,
                 "bill": _bill_label(bill), "party_orientation": orientation},
            )  # fmt: skip
        if rec is not None:
            rec.choice, rec.party_orientation = VoteChoice(choice), orientation
        n += 1
    return n


def _bill_label(bill: Bill | None) -> str | None:
    if not bill:
        return None
    return bill_label(bill)


async def _fetch_camara_vote(api: cam.CamaraSource, v: dict):
    """Votos nominais + orientação + detalhe de uma votação; None se simbólica ou com erro."""
    vid = str(v["id"])
    try:
        votos = await api.votos(vid)
    except Exception as e:  # noqa: BLE001 — um item quebrado na fonte não derruba o job
        log.warning("votação %s ignorada: %s", vid, e)
        return None
    if not votos:
        return None  # votação simbólica: sem voto nominal
    orient, detail = await asyncio.gather(
        api.orientacoes(vid), api.votacao(vid), return_exceptions=True
    )
    orient = [] if isinstance(orient, BaseException) else orient
    detail = {} if isinstance(detail, BaseException) else detail
    return v, votos, orient, detail


async def sync_camara(api: cam.CamaraSource) -> None:
    async with tracked("sync_votes", "camara") as run, SessionLocal() as db:
        pols = await politician_index(db, House.camara)
        # Só o Plenário: em comissões só votam os membros, e "ausente" não faria sentido.
        for start, end in await window(db, House.camara):
            votacoes = [v async for v in api.votacoes(start, end, id_orgao=cam.PLENARIO_ID)]
            # Busca em paralelo (limitado pelo HttpClient); grava em sequência, bloco a bloco.
            fetched = await asyncio.gather(*(_fetch_camara_vote(api, v) for v in votacoes))
            for item in fetched:
                if item:
                    run.items += await _save_camara_vote(db, item, pols)
                    await db.commit()


async def _save_camara_vote(db, item, pols: dict[str, Politician]) -> int:
    v, votos, orient, detail = item
    vid = str(v["id"])
    orient_by_party = orientation_by_party(orient)
    choices = {}
    for row in votos:
        dep = row.get("deputado_") or {}
        party = (dep.get("siglaPartido") or "").upper()
        choices[str(dep.get("id"))] = (
            cam.map_vote(row.get("tipoVoto")),
            orient_by_party.get(party),
        )
    bill = None
    afetadas = detail.get("proposicoesAfetadas") or []
    if afetadas:
        pa = afetadas[0]
        bill, _ = await upsert(
            db,
            Bill,
            {"house": House.camara, "external_id": str(pa["id"])},
            {
                "type": pa.get("siglaTipo") or "PROP",
                "number": pa.get("numero"),
                "year": pa.get("ano"),
                "official_summary": pa.get("ementa"),
                "url": bill_url(House.camara, str(pa["id"])),
            },
        )
    voted_at = parse_dt(v.get("dataHoraRegistro")) or parse_dt(v.get("data"))
    result = (
        "Aprovada"
        if v.get("aprovacao") == 1
        else ("Rejeitada" if v.get("aprovacao") == 0 else None)
    )
    return await _save_vote(
        db, House.camara, vid, voted_at, v.get("descricao"), result, bill, choices, pols
    )


async def sync_senado(api: sen.SenadoSource) -> None:
    async with tracked("sync_votes", "senado") as run, SessionLocal() as db:
        pols = await politician_index(db, House.senado)
        votacoes = []
        for start, end in await window(db, House.senado):
            votacoes += await api.votacoes(start, end)
        # Comparecimento por sessão: escolhas de cada senador em todas as votações da sessão.
        sessions: dict[str, dict] = {}
        for v in votacoes:
            votos = sen.as_list(v.get("votos"))
            if not votos:
                continue
            ext = str(v.get("codigoSessaoVotacao") or v.get("codigoVotacao"))
            choices: dict[str, tuple[str, str | None]] = {}
            listed: set[str] = set()
            sess = sessions.setdefault(
                str(v.get("codigoSessao")),
                {"date": v.get("dataSessao"), "type": v.get("siglaTipoSessao"), "by": {}},
            )
            for i in votos:
                code = str(i.get("codigoParlamentar"))
                listed.add(code)
                choice = sen.map_vote(i.get("siglaVotoParlamentar"))
                if choice:
                    choices[code] = (choice, None)
                    entry = sess["by"].setdefault(code, {"choices": [], "why": None})
                    entry["choices"].append(choice)
                    if choice == "justificada":
                        entry["why"] = i.get("descricaoVotoParlamentar") or i.get(
                            "siglaVotoParlamentar"
                        )
            bill = None
            if v.get("codigoMateria"):
                code = str(v["codigoMateria"])
                tipo, numero, ano = parse_identificacao(v.get("identificacao"))
                bill, _ = await upsert(
                    db,
                    Bill,
                    {"house": House.senado, "external_id": code},
                    {
                        "type": tipo or v.get("siglaTipoMateria") or "MAT",
                        "number": numero or _int(v.get("numeroMateria")),
                        "year": ano or _int(v.get("ano")),
                        "official_summary": v.get("ementa"),
                        "url": bill_url(House.senado, code),
                    },
                )
            voted_at = parse_dt(v.get("dataSessao")) or datetime.now(UTC)
            run.items += await _save_vote(
                db, House.senado, ext, voted_at, v.get("descricaoVotacao"),
                senado_result(v.get("resultadoVotacao")), bill, choices, pols, listed,
            )  # fmt: skip
            await db.commit()
        await _save_senado_attendance(db, sessions, pols)


async def _save_senado_attendance(db, sessions: dict[str, dict], pols) -> None:
    """Sessões com votação nominal viram sessões deliberativas com presença por senador."""
    for code, info in sessions.items():
        starts = parse_dt(info["date"])
        if not starts:
            continue
        sess, _ = await upsert(
            db,
            Session,
            {"house": House.senado, "external_id": code},
            {
                "type": info["type"],
                "is_deliberative": True,
                "starts_at": starts,
                "title": f"Sessão deliberativa {info['type'] or ''}".strip(),
            },
        )
        existing = {
            a.politician_id: a
            for a in (
                await db.execute(select(Attendance).where(Attendance.session_id == sess.id))
            ).scalars()
        }
        for ext, entry in info["by"].items():
            p = pols.get(ext)
            status = sen.session_attendance(entry["choices"])
            if not p or not status:
                continue
            why = entry["why"] if status == "justificada" else None
            a = existing.get(p.id)
            if a is None:
                db.add(
                    Attendance(
                        session_id=sess.id,
                        politician_id=p.id,
                        status=AttendanceStatus(status),
                        justification=why,
                    )
                )
            else:
                a.status, a.justification = AttendanceStatus(status), why
        await db.commit()


def _int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


async def run(camara: cam.CamaraSource, senado: sen.SenadoSource) -> None:
    await sync_camara(camara)
    await sync_senado(senado)

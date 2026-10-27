"""2 · Votações do período + votos nominais + orientação de bancada."""

from __future__ import annotations

import asyncio
import re
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Bill, FeedType, House, Politician, Vote, VoteChoice, VoteRecord
from app.services.feed import add_event
from app.services.news_matching import normalize
from app.services.presenters import bill_url
from ingestion.jobs.common import parse_dt, politician_index, tracked, upsert
from ingestion.jobs.sync_bills import bill_label
from ingestion.sources import camara as cam
from ingestion.sources import senado as sen

SENADO_RESULT = {"A": "Aprovada", "R": "Rejeitada"}


def senado_result(code: str | None) -> str | None:
    return SENADO_RESULT.get((code or "").upper(), code)


def window() -> tuple[date, date]:
    today = datetime.now(UTC).date()
    return today - timedelta(days=get_settings().sync_days_back), today


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
) -> int:
    """Grava votação + votos nominais. `choices`: external_id → (escolha, orientação)."""
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
    # Quem estava em exercício e não aparece na lista nominal fica como ausente.
    for ext, p in pols.items():
        if p.in_office and ext not in choices:
            choices[ext] = ("ausente", None)

    existing = {
        r.politician_id: r
        for r in (
            await db.execute(select(VoteRecord).where(VoteRecord.vote_id == vote.id))
        ).scalars()
    }
    title = (bill.official_summary if bill else None) or description or "Votação"
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
            await add_event(
                db, p.id, FeedType.vote, vote.id, voted_at,
                {"title": title[:300], "choice": choice, "result": result,
                 "bill": _bill_label(bill), "party_orientation": orientation},
            )  # fmt: skip
        else:
            rec.choice, rec.party_orientation = VoteChoice(choice), orientation
        n += 1
    return n


def _bill_label(bill: Bill | None) -> str | None:
    if not bill:
        return None
    return bill_label(bill)


async def sync_camara(api: cam.CamaraSource) -> None:
    start, end = window()
    async with tracked("sync_votes", "camara") as run, SessionLocal() as db:
        pols = await politician_index(db, House.camara)
        votacoes = [v async for v in api.votacoes(start, end)]
        for v in votacoes:
            # Só o Plenário: em comissões só votam os membros, e "ausente" não faria sentido.
            if (v.get("siglaOrgao") or "").upper() != "PLEN":
                continue
            vid = str(v["id"])
            votos, orient, detail = await asyncio.gather(
                api.votos(vid), api.orientacoes(vid), api.votacao(vid)
            )
            if not votos:
                continue  # votação simbólica: sem voto nominal
            orient_by_party = orientation_by_party(orient)
            choices = {}
            for item in votos:
                dep = item.get("deputado_") or {}
                party = (dep.get("siglaPartido") or "").upper()
                choices[str(dep.get("id"))] = (
                    cam.map_vote(item.get("tipoVoto")),
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
            run.items += await _save_vote(
                db, House.camara, vid, voted_at, v.get("descricao"), result, bill, choices, pols
            )
            await db.commit()


async def sync_senado(api: sen.SenadoSource) -> None:
    start, end = window()
    async with tracked("sync_votes", "senado") as run, SessionLocal() as db:
        pols = await politician_index(db, House.senado)
        for v in await api.votacoes(start, end):
            votos = sen.as_list(v.get("votos"))
            if not votos:
                continue
            ext = str(v.get("codigoSessaoVotacao") or v.get("codigoVotacao"))
            choices = {
                str(i.get("codigoParlamentar")): (
                    sen.map_vote(
                        i.get("siglaVotoParlamentar") or i.get("descricaoVotoParlamentar")
                    ),
                    None,
                )
                for i in votos
            }
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
                senado_result(v.get("resultadoVotacao")), bill, choices, pols,
            )  # fmt: skip
            await db.commit()


def _int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


async def run(camara: cam.CamaraSource, senado: sen.SenadoSource) -> None:
    await sync_camara(camara)
    await sync_senado(senado)

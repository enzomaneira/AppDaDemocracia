"""Converte modelos em schemas e monta links para a fonte oficial (rastreabilidade)."""

from __future__ import annotations

from app.models import Bill, House, Politician, Vote
from app.schemas import BillOut, PoliticianSummary, VoteOut


def politician_official_url(p: Politician) -> str:
    if p.house == House.camara:
        return f"https://www.camara.leg.br/deputados/{p.external_id}"
    return f"https://www25.senado.leg.br/web/senadores/senador/-/perfil/{p.external_id}"


def vote_source_url(v: Vote) -> str:
    if v.house == House.camara:
        return f"https://dadosabertos.camara.leg.br/api/v2/votacoes/{v.external_id}"
    return f"https://legis.senado.leg.br/dadosabertos/votacao?codigoSessaoVotacao={v.external_id}"


def bill_url(house: House, external_id: str) -> str:
    if house == House.camara:
        return (
            f"https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao={external_id}"
        )
    return f"https://www25.senado.leg.br/web/atividade/materias/-/materia/{external_id}"


def politician_summary(p: Politician) -> PoliticianSummary:
    return PoliticianSummary(
        id=p.id,
        slug=p.slug,
        house=p.house.value,
        name=p.parliamentary_name,
        party=p.party.acronym if p.party else None,
        uf=p.uf,
        photo_url=p.photo_url,
        in_office=p.in_office,
    )


def vote_out(v: Vote) -> VoteOut:
    bill: Bill | None = v.bill
    return VoteOut(
        id=v.id,
        house=v.house.value,
        voted_at=v.voted_at,
        description=v.description,
        result=v.result,
        yes_count=v.yes_count,
        no_count=v.no_count,
        abstention_count=v.abstention_count,
        bill=BillOut.model_validate(bill) if bill else None,
        source_url=vote_source_url(v),
    )

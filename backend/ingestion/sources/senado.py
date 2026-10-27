"""Senado Federal · Dados Abertos (XML por padrão; JSON via header Accept).

Docs: https://legis.senado.leg.br/dadosabertos/docs/
Os formatos abaixo devem ser conferidos na documentação oficial antes de produção
(questão em aberto do projeto); o parsing é defensivo para tolerar campos ausentes.
"""

from __future__ import annotations

import csv
import io
from datetime import date
from typing import Any

from app.core.config import get_settings
from ingestion.http import HttpClient

VOTE_MAP = {
    "sim": "sim",
    "nao": "nao",
    "não": "nao",
    "abstencao": "abstencao",
    "abstenção": "abstencao",
    "obstrucao": "obstrucao",
    "p-ob": "obstrucao",
    "ap": "ausente",
    "ns": "ausente",
}


def as_list(value: Any) -> list:
    """O JSON do Senado vira objeto quando há um único item; normaliza para lista."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


class SenadoSource:
    def __init__(self, client: HttpClient | None = None) -> None:
        self.client = client or HttpClient(
            get_settings().senado_base_url, headers={"Accept": "application/json"}
        )

    async def senadores_em_exercicio(self) -> list[dict]:
        data = await self.client.get_json("/senador/lista/atual")
        parl = data.get("ListaParlamentarEmExercicio", {}).get("Parlamentares", {})
        return as_list(parl.get("Parlamentar"))

    async def votacoes(self, start: date, end: date) -> list[dict]:
        data = await self.client.get_json(
            "/votacao", {"dataInicio": start.isoformat(), "dataFim": end.isoformat()}
        )
        return as_list(data)

    async def agenda(self, day: date) -> list[dict]:
        data = await self.client.get_json(f"/agenda/{day:%Y%m%d}")
        sessoes = data.get("AgendaPlenario", {}).get("Sessoes", {})
        return as_list(sessoes.get("Sessao"))

    async def ceaps_csv(self, ano: int) -> list[dict[str, str]]:
        """CSV anual de gastos (CEAPS): latin-1, separador ';', 1ª linha é metadado."""
        url = f"https://www.senado.leg.br/transparencia/LAI/verba/despesa_ceaps_{ano}.csv"
        # O portal de transparência recusa (406) o Accept: application/json do cliente padrão.
        r = await self.client.get(url, headers={"Accept": "text/csv,*/*"})
        text = r.content.decode("latin-1")
        lines = text.splitlines()
        if lines and lines[0].lstrip('"').upper().startswith("ULTIMA ATUALIZACAO"):
            lines = lines[1:]
        return list(csv.DictReader(io.StringIO("\n".join(lines)), delimiter=";"))

    async def aclose(self) -> None:
        await self.client.aclose()


def parse_senador(item: dict) -> dict:
    ident = item.get("IdentificacaoParlamentar", {})
    mandato = item.get("Mandato", {})
    return {
        "external_id": str(ident.get("CodigoParlamentar")),
        "parliamentary_name": ident.get("NomeParlamentar") or "",
        "civil_name": ident.get("NomeCompletoParlamentar") or ident.get("NomeParlamentar") or "",
        "party": ident.get("SiglaPartidoParlamentar"),
        # Na lista de senadores, a UF vem do bloco de mandato.
        "uf": mandato.get("UfParlamentar") or ident.get("UfParlamentar") or "",
        "photo_url": ident.get("UrlFotoParlamentar"),
        "email": ident.get("EmailParlamentar"),
        "social_links": [ident["UrlPaginaParlamentar"]]
        if ident.get("UrlPaginaParlamentar")
        else [],
    }


def map_vote(sigla: str | None) -> str:
    return VOTE_MAP.get((sigla or "").strip().lower(), "ausente")

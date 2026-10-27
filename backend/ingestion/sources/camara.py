"""Câmara dos Deputados · API Dados Abertos v2 (JSON, sem autenticação).

Docs: https://dadosabertos.camara.leg.br/swagger/api.html
"""

from __future__ import annotations

import csv
import io
import zipfile
from collections.abc import AsyncIterator
from datetime import date
from typing import Any

from app.core.config import get_settings
from app.services.news_matching import normalize
from ingestion.http import HttpClient

ITENS = 100

# Valores de tipoVoto da Câmara → enum interno.
VOTE_MAP = {
    "sim": "sim",
    "não": "nao",
    "nao": "nao",
    "abstenção": "abstencao",
    "abstencao": "abstencao",
    "obstrução": "obstrucao",
    "obstrucao": "obstrucao",
    "artigo 17": "art17",
    "art. 17": "art17",
}


class CamaraSource:
    def __init__(self, client: HttpClient | None = None) -> None:
        self.client = client or HttpClient(
            get_settings().camara_base_url, headers={"Accept": "application/json"}
        )

    async def _paginate(self, path: str, params: dict[str, Any]) -> AsyncIterator[dict]:
        page = 1
        while True:
            data = await self.client.get_json(path, {**params, "itens": ITENS, "pagina": page})
            for item in data.get("dados", []):
                yield item
            if not any(link.get("rel") == "next" for link in data.get("links", [])):
                break
            page += 1

    def deputados(self, legislatura: int) -> AsyncIterator[dict]:
        return self._paginate("/deputados", {"idLegislatura": legislatura, "ordem": "ASC"})

    async def deputado(self, dep_id: int | str) -> dict:
        return (await self.client.get_json(f"/deputados/{dep_id}"))["dados"]

    def votacoes(self, start: date, end: date) -> AsyncIterator[dict]:
        return self._paginate(
            "/votacoes",
            {"dataInicio": start.isoformat(), "dataFim": end.isoformat(), "ordem": "ASC"},
        )

    async def votacao(self, vot_id: str) -> dict:
        return (await self.client.get_json(f"/votacoes/{vot_id}"))["dados"]

    async def votos(self, vot_id: str) -> list[dict]:
        return (await self.client.get_json(f"/votacoes/{vot_id}/votos"))["dados"]

    async def orientacoes(self, vot_id: str) -> list[dict]:
        return (await self.client.get_json(f"/votacoes/{vot_id}/orientacoes"))["dados"]

    def eventos(self, start: date, end: date) -> AsyncIterator[dict]:
        return self._paginate(
            "/eventos", {"dataInicio": start.isoformat(), "dataFim": end.isoformat()}
        )

    async def evento_deputados(self, ev_id: int | str) -> list[dict]:
        return (await self.client.get_json(f"/eventos/{ev_id}/deputados"))["dados"]

    def deputado_eventos(self, dep_id: int | str, start: date, end: date) -> AsyncIterator[dict]:
        return self._paginate(
            f"/deputados/{dep_id}/eventos",
            {"dataInicio": start.isoformat(), "dataFim": end.isoformat()},
        )

    def proposicoes_autor(self, dep_id: int | str, start: date) -> AsyncIterator[dict]:
        return self._paginate(
            "/proposicoes",
            {"idDeputadoAutor": dep_id, "dataApresentacaoInicio": start.isoformat()},
        )

    def despesas(self, dep_id: int | str, ano: int, mes: int | None = None) -> AsyncIterator[dict]:
        params: dict[str, Any] = {"ano": ano}
        if mes:
            params["mes"] = mes
        return self._paginate(f"/deputados/{dep_id}/despesas", params)

    async def ceap_csv(self, ano: int) -> list[dict[str, str]]:
        """Arquivo anual da cota parlamentar (CSV dentro de um zip, separador ';')."""
        r = await self.client.get(
            f"https://www.camara.leg.br/cotas/Ano-{ano}.csv.zip", headers={"Accept": "*/*"}
        )
        with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
            name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
            text = zf.read(name).decode("utf-8-sig")
        return list(csv.DictReader(io.StringIO(text), delimiter=";"))

    async def aclose(self) -> None:
        await self.client.aclose()


def map_vote(tipo: str | None) -> str:
    return VOTE_MAP.get((tipo or "").strip().lower(), "ausente")


def is_plenary_deliberative(evento: dict) -> bool:
    """Sessão deliberativa do Plenário (base do cálculo de presença).

    Questão em aberto do projeto: validar contra a página oficial de frequência.
    """
    tipo = normalize(evento.get("descricaoTipo") or "")
    orgaos = [o.get("sigla", "").upper() for o in evento.get("orgaos") or []]
    deliberative = "deliberativa" in tipo and "nao deliberativa" not in tipo
    return deliberative and "PLEN" in orgaos

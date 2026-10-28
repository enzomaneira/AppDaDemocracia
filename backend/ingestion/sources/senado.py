"""Senado Federal · Dados Abertos (XML por padrão; JSON via header Accept).

Docs: https://legis.senado.leg.br/dadosabertos/docs/ (spec em /v3/api-docs).
O parsing é defensivo para tolerar campos ausentes.

O Senado não publica presença por sessão: o comparecimento de cada senador vem no
registro de cada votação nominal (siglaVotoParlamentar), com os 81 senadores listados.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import UTC, date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.core.config import get_settings
from app.services.news_matching import normalize
from ingestion.http import HttpClient

# siglaVotoParlamentar (normalizada) → escolha interna. Códigos fora da tabela são ignorados
# (ex.: "NA", "dispositivo não citado"): não viram voto nem falta.
VOTE_MAP = {
    "sim": "sim",
    "nao": "nao",
    "abstencao": "abstencao",
    "obstrucao": "obstrucao",
    "p-od": "obstrucao",  # presente, obstrução declarada
    "votou": "secreto",  # escrutínio secreto: participou, voto não é público
    "p-nrv": "presente",  # presente, não registrou voto
    "presidente (art. 51 risf)": "art17",  # presidindo a sessão
    # Ausências justificadas
    "ap": "justificada",  # atividade parlamentar
    "mis": "justificada",  # missão da Casa no país/exterior
    "ls": "justificada",  # licença saúde
    "lp": "justificada",  # licença particular
    "lg": "justificada",  # licença gestante
    "la": "justificada",  # licença
    "lap": "justificada",  # licença para atividade parlamentar
    "rep": "justificada",  # representação da Casa
    # Falta
    "ncom": "ausente",  # não compareceu
}

PRESENT = {"sim", "nao", "abstencao", "obstrucao", "secreto", "presente", "art17"}


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

    async def processos_autor(self, codigo: str, start: date) -> list[dict]:
        """Processos de autoria ou coautoria do senador apresentados desde `start`."""
        data = await self.client.get_json(
            "/processo",
            {"codigoParlamentarAutor": codigo, "dataInicioApresentacao": start.isoformat()},
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


def map_vote(sigla: str | None) -> str | None:
    """Código do Senado → escolha interna; None para códigos que não indicam voto nem falta."""
    return VOTE_MAP.get(normalize(sigla or ""))


def session_attendance(choices: list[str]) -> str | None:
    """Comparecimento do senador na sessão, a partir das suas escolhas nas votações dela.

    Presente se esteve presente em alguma votação; senão, ausência justificada se houve
    justificativa; senão, falta. Sem nenhum código conhecido, não conta.
    """
    if any(c in PRESENT for c in choices):
        return "presente"
    if "justificada" in choices:
        return "justificada"
    if "ausente" in choices:
        return "ausente"
    return None


def parse_processo(item: dict) -> dict | None:
    """Item de /processo → campos de Bill; None se a identificação não for 'TIPO N/AAAA'."""
    m = re.match(r"\s*([A-Za-z]+)\s+(\d+)/(\d{4})", item.get("identificacao") or "")
    if not m or not item.get("codigoMateria"):
        return None
    return {
        "external_id": str(item["codigoMateria"]),
        "type": m.group(1).upper(),
        "number": int(m.group(2)),
        "year": int(m.group(3)),
        "official_summary": item.get("ementa"),
        "presented_at": _parse_date(item.get("dataApresentacao")),
    }


def _parse_date(value: str | None):
    """'2026-09-01' → datetime em UTC (meio-dia de Brasília, para não trocar de dia)."""
    if not value:
        return None
    try:
        d = datetime.fromisoformat(value[:10])
    except ValueError:
        return None
    return d.replace(hour=12, tzinfo=ZoneInfo("America/Sao_Paulo")).astimezone(UTC)

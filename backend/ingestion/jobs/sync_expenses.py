"""5 · Cota parlamentar: CEAP (Câmara) e CEAPS (Senado), a partir dos arquivos anuais.

O arquivo anual é mais eficiente que uma chamada por deputado (e o endpoint
/deputados/{id}/despesas pode vir vazio). Cada execução substitui os lançamentos do ano
pelo conteúdo do arquivo oficial.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Expense, House, Politician
from app.services.news_matching import normalize
from app.services.stats import legislature_start_year
from ingestion.jobs.common import politician_index, tracked
from ingestion.sources.camara import CamaraSource
from ingestion.sources.senado import SenadoSource


def row_key(*parts) -> str:
    return hashlib.sha1("|".join(str(p) for p in parts).encode()).hexdigest()


def parse_brl(value: str | None) -> Decimal:
    """'1.234,56' ou '1234.56' → Decimal."""
    if not value:
        return Decimal(0)
    v = value.strip()
    if "," in v:
        v = v.replace(".", "").replace(",", ".")
    try:
        return Decimal(v)
    except InvalidOperation:
        return Decimal(0)


def _int(value: str | None, default: int) -> int:
    try:
        return int(value or default)
    except ValueError:
        return default


async def years_to_sync(db, house: House) -> list[int]:
    """Anos de arquivo a (re)carregar.

    Sempre o ano corrente (e o anterior em janeiro, quando chegam notas de dezembro), mais
    qualquer ano da legislatura que ainda não tenha dados. SYNC_SINCE recarrega desde o ano dado.
    """
    s = get_settings()
    today = datetime.now(UTC).date()
    first_leg = legislature_start_year(s.legislature)
    present = set(
        (
            await db.execute(
                select(Expense.year)
                .join(Politician, Politician.id == Expense.politician_id)
                .where(Politician.house == house)
                .distinct()
            )
        ).scalars()
    )
    years = {today.year} | ({today.year - 1} if today.month == 1 else set())
    years |= {y for y in range(first_leg, today.year + 1) if y not in present}
    if s.sync_since:
        years |= set(range(s.sync_since.year, today.year + 1))
    return sorted(years)


def keyed_rows(rows: list[dict[str, str]], prefix: str, year: int):
    """(chave, linha) para cada linha do arquivo anual.

    Os ids da fonte não são únicos (ideDocumento é "0" em milhares de linhas e se repete
    entre lançamentos diferentes, como uma passagem e o seu estorno). A chave é o conteúdo
    da linha, com um contador para linhas idênticas: nenhuma linha legítima é descartada.
    """
    seen: Counter[str] = Counter()
    for row in rows:
        base = row_key(*(f"{k}={row.get(k)}" for k in sorted(row, key=str)))
        seen[base] += 1
        yield f"{prefix}:{year}:{base}:{seen[base]}", row


async def _replace_year(db, house: House, year: int, expenses: list[Expense]) -> int:
    """O arquivo anual é a fonte da verdade: troca os lançamentos do ano pelo conteúdo dele."""
    ids = select(Politician.id).where(Politician.house == house)
    await db.execute(delete(Expense).where(Expense.year == year, Expense.politician_id.in_(ids)))
    db.add_all(expenses)
    await db.commit()
    return len(expenses)


async def sync_camara(api: CamaraSource) -> None:
    async with tracked("sync_expenses", "camara") as run, SessionLocal() as db:
        pols = await politician_index(db, House.camara)
        for year in await years_to_sync(db, House.camara):
            run.items += await _camara_year(db, api, pols, year)


async def _camara_year(db, api: CamaraSource, pols, year: int) -> int:
    expenses = []
    for key, row in keyed_rows(await api.ceap_csv(year), "camara", year):
        p = pols.get((row.get("ideCadastro") or "").strip())
        if not p:
            continue
        expenses.append(
            Expense(
                external_id=key,
                politician_id=p.id,
                year=year,
                month=_int(row.get("numMes"), 1),
                category=(row.get("txtDescricao") or "Outros").strip(),
                supplier=row.get("txtFornecedor"),
                amount=parse_brl(row.get("vlrLiquido")),
                document_url=row.get("urlDocumento") or None,
            )
        )
    return await _replace_year(db, House.camara, year, expenses)


async def sync_senado(api: SenadoSource) -> None:
    async with tracked("sync_expenses", "senado") as run, SessionLocal() as db:
        pols = await politician_index(db, House.senado)
        # Ligação por nome normalizado (sem acentos), como previsto no projeto.
        by_name = {}
        for p in pols.values():
            by_name[normalize(p.parliamentary_name)] = p
            by_name[normalize(p.civil_name)] = p
        for year in await years_to_sync(db, House.senado):
            run.items += await _senado_year(db, api, by_name, year)


async def _senado_year(db, api: SenadoSource, by_name, year: int) -> int:
    expenses = []
    for key, row in keyed_rows(await api.ceaps_csv(year), "senado", year):
        p = by_name.get(normalize(row.get("SENADOR") or ""))
        if not p:
            continue
        expenses.append(
            Expense(
                external_id=key,
                politician_id=p.id,
                year=year,
                month=_int(row.get("MES"), 1),
                category=row.get("TIPO_DESPESA") or "Outros",
                supplier=row.get("FORNECEDOR"),
                amount=parse_brl(row.get("VALOR_REEMBOLSADO")),
            )
        )
    return await _replace_year(db, House.senado, year, expenses)


async def run(camara: CamaraSource, senado: SenadoSource) -> None:
    await sync_camara(camara)
    await sync_senado(senado)

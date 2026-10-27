"""5 · Cota parlamentar: CEAP (Câmara) e CEAPS (Senado), a partir dos arquivos anuais.

O arquivo anual é mais eficiente que uma chamada por deputado (e o endpoint
/deputados/{id}/despesas pode vir vazio). Só documentos novos são inseridos.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Expense, House
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


async def _existing_keys(db, prefix: str, year: int) -> set[str]:
    q = select(Expense.external_id).where(
        Expense.year == year, Expense.external_id.like(f"{prefix}:%")
    )
    return set((await db.execute(q)).scalars())


async def years_to_sync(db, prefix: str) -> list[int]:
    """Anos de arquivo a baixar: legislatura toda se não há gastos (ou SYNC_SINCE); senão o
    ano corrente, mais o anterior em janeiro (notas de dezembro chegam com atraso)."""
    s = get_settings()
    today = datetime.now(UTC).date()
    q = select(Expense.external_id).where(Expense.external_id.like(f"{prefix}:%")).limit(1)
    if s.sync_since:
        first = s.sync_since.year
    elif (await db.execute(q)).first() is None:
        first = legislature_start_year(s.legislature)
    else:
        first = today.year - 1 if today.month == 1 else today.year
    return list(range(first, today.year + 1))


async def sync_camara(api: CamaraSource) -> None:
    async with tracked("sync_expenses", "camara") as run, SessionLocal() as db:
        pols = await politician_index(db, House.camara)
        for year in await years_to_sync(db, "camara"):
            run.items += await _camara_year(db, api, pols, year)


async def _camara_year(db, api: CamaraSource, pols, year: int) -> int:
    n = 0
    seen = await _existing_keys(db, "camara", year)
    for row in await api.ceap_csv(year):
        p = pols.get((row.get("ideCadastro") or "").strip())
        if not p:
            continue
        key = "camara:" + (row.get("ideDocumento") or row_key(*(row.get(k) for k in sorted(row))))
        if key in seen:
            continue
        seen.add(key)
        db.add(
            Expense(
                external_id=key,
                politician_id=p.id,
                year=_int(row.get("numAno"), year),
                month=_int(row.get("numMes"), 1),
                category=(row.get("txtDescricao") or "Outros").strip(),
                supplier=row.get("txtFornecedor"),
                amount=parse_brl(row.get("vlrLiquido")),
                document_url=row.get("urlDocumento") or None,
            )
        )
        n += 1
    await db.commit()
    return n


async def sync_senado(api: SenadoSource) -> None:
    async with tracked("sync_expenses", "senado") as run, SessionLocal() as db:
        pols = await politician_index(db, House.senado)
        # Ligação por nome normalizado (sem acentos), como previsto no projeto.
        by_name = {}
        for p in pols.values():
            by_name[normalize(p.parliamentary_name)] = p
            by_name[normalize(p.civil_name)] = p
        for year in await years_to_sync(db, "senado"):
            run.items += await _senado_year(db, api, by_name, year)


async def _senado_year(db, api: SenadoSource, by_name, year: int) -> int:
    n = 0
    seen = await _existing_keys(db, "senado", year)
    for row in await api.ceaps_csv(year):
        p = by_name.get(normalize(row.get("SENADOR") or ""))
        if not p:
            continue
        key = "senado:" + (row.get("COD_DOCUMENTO") or row_key(*row.values()))
        if key in seen:
            continue
        seen.add(key)
        db.add(
            Expense(
                external_id=key,
                politician_id=p.id,
                year=_int(row.get("ANO"), year),
                month=_int(row.get("MES"), 1),
                category=row.get("TIPO_DESPESA") or "Outros",
                supplier=row.get("FORNECEDOR"),
                amount=parse_brl(row.get("VALOR_REEMBOLSADO")),
            )
        )
        n += 1
    await db.commit()
    return n


async def run(camara: CamaraSource, senado: SenadoSource) -> None:
    await sync_camara(camara)
    await sync_senado(senado)

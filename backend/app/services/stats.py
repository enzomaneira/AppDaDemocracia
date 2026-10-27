"""Cálculo das métricas de performance (RF07).

Regras de negócio (ver página "Como calculamos"):
- Presença = sessões deliberativas com presença ÷ sessões deliberativas do período.
- Ausências justificadas aparecem separadas e nunca são somadas às faltas.
- Toda métrica vem acompanhada do período e da média da casa.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import and_, case, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    PARTICIPATED_CHOICES,
    Attendance,
    AttendanceStatus,
    AuthorRole,
    Bill,
    BillAuthor,
    Expense,
    House,
    Politician,
    PoliticianStats,
    Session,
    Vote,
    VoteRecord,
)

# Início de cada legislatura (1º de fevereiro do ano seguinte à eleição; 4 anos de duração).
LEGISLATURE_57_START_YEAR = 2023

# Tipos que contam como "proposição apresentada": projetos de lei, de lei complementar,
# de emenda à Constituição, de decreto legislativo e de resolução (PRC: Câmara; PRS: Senado).
STATS_BILL_TYPES = ("PL", "PLP", "PEC", "PDL", "PRC", "PRS")


@dataclass(frozen=True)
class Period:
    key: str
    start: datetime
    end: datetime
    label: str


def legislature_start_year(legislature: int) -> int:
    return LEGISLATURE_57_START_YEAR + (legislature - 57) * 4


def parse_period(key: str | None, legislature: int) -> Period:
    """`leg57` (padrão: legislatura atual) ou um ano como `2026`."""
    key = key or f"leg{legislature}"
    if key.startswith("leg"):
        leg = int(key[3:])
        y = legislature_start_year(leg)
        return Period(
            key,
            datetime(y, 2, 1, tzinfo=UTC),
            datetime(y + 4, 2, 1, tzinfo=UTC),
            f"{leg}ª legislatura ({y}–{y + 4})",
        )
    year = int(key)
    if not 1990 <= year <= 2100:
        raise ValueError("ano fora do intervalo")
    return Period(key, datetime(year, 1, 1, tzinfo=UTC), datetime(year + 1, 1, 1, tzinfo=UTC), key)


def attendance_rate(present: int, total: int) -> float | None:
    """Percentual de presença com duas casas decimais; None quando não houve sessão."""
    if total <= 0:
        return None
    return round(present / total * 100, 2)


def unjustified_absences(total: int, present: int, justified: int) -> int:
    return max(total - present - justified, 0)


def house_average(values: list[float | int | Decimal | None]) -> float | None:
    nums = [float(v) for v in values if v is not None]
    if not nums:
        return None
    return round(sum(nums) / len(nums), 2)


def build_house_averages(rows: list[dict]) -> dict[House, dict[str, float | None]]:
    """Média da casa por métrica, calculada só entre parlamentares da mesma casa."""
    metrics = ["attendance_rate", "votes_participated", "bills_authored", "expenses_total"]
    out: dict[House, dict[str, float | None]] = {}
    for house in House:
        same = [r for r in rows if r["house"] == house]
        out[house] = {m: house_average([r[m] for r in same]) for m in metrics}
    return out


async def compute_all(db: AsyncSession, period: Period) -> int:
    """Recalcula politician_stats para um período. Retorna quantas linhas gravou."""
    in_period_session = and_(Session.starts_at >= period.start, Session.starts_at < period.end)
    att_q = (
        select(
            Attendance.politician_id,
            func.count().label("total"),
            func.sum(case((Attendance.status == AttendanceStatus.presente, 1), else_=0)).label(
                "present"
            ),
            func.sum(case((Attendance.status == AttendanceStatus.justificada, 1), else_=0)).label(
                "justified"
            ),
        )
        .join(Session, Session.id == Attendance.session_id)
        .where(Session.is_deliberative.is_(True), in_period_session)
        .group_by(Attendance.politician_id)
    )
    att = {r.politician_id: r for r in (await db.execute(att_q)).all()}

    in_period_vote = and_(Vote.voted_at >= period.start, Vote.voted_at < period.end)
    votes_q = (
        select(
            VoteRecord.politician_id,
            func.count().label("total"),
            func.sum(case((VoteRecord.choice.in_(PARTICIPATED_CHOICES), 1), else_=0)).label("part"),
        )
        .join(Vote, Vote.id == VoteRecord.vote_id)
        .where(in_period_vote)
        .group_by(VoteRecord.politician_id)
    )
    votes = {r.politician_id: r for r in (await db.execute(votes_q)).all()}

    # Só projetos contam como proposição apresentada (não requerimentos, pareceres etc.).
    bills_q = (
        select(BillAuthor.politician_id, BillAuthor.role, func.count())
        .join(Bill, Bill.id == BillAuthor.bill_id)
        .where(Bill.type.in_(STATS_BILL_TYPES))
        .group_by(BillAuthor.politician_id, BillAuthor.role)
    )
    bills: dict[uuid.UUID, dict[AuthorRole, int]] = {}
    for pid, role, n in (await db.execute(bills_q)).all():
        bills.setdefault(pid, {})[role] = n

    exp_q = (
        select(Expense.politician_id, func.sum(Expense.amount))
        .where(
            (Expense.year * 100 + Expense.month) >= period.start.year * 100 + period.start.month,
            (Expense.year * 100 + Expense.month) < period.end.year * 100 + period.end.month,
        )
        .group_by(Expense.politician_id)
    )
    expenses = dict((await db.execute(exp_q)).all())

    politicians = (await db.execute(select(Politician.id, Politician.house))).all()
    rows: list[dict] = []
    for pid, house in politicians:
        a = att.get(pid)
        v = votes.get(pid)
        total, present, justified = (
            (a.total, int(a.present or 0), int(a.justified or 0)) if a else (0, 0, 0)
        )
        rows.append(
            {
                "politician_id": pid,
                "house": house,
                "sessions_total": total,
                "sessions_present": present,
                "sessions_justified": justified,
                "attendance_rate": attendance_rate(present, total),
                "votes_total": v.total if v else 0,
                "votes_participated": int(v.part or 0) if v else 0,
                "bills_authored": bills.get(pid, {}).get(AuthorRole.autor, 0),
                "bills_reported": bills.get(pid, {}).get(AuthorRole.relator, 0),
                "expenses_total": Decimal(expenses.get(pid) or 0),
            }
        )

    averages = build_house_averages(rows)
    await db.execute(delete(PoliticianStats).where(PoliticianStats.period == period.key))
    now = datetime.now(UTC)
    for r in rows:
        house = r.pop("house")
        db.add(PoliticianStats(period=period.key, house_avg=averages[house], computed_at=now, **r))
    await db.commit()
    return len(rows)

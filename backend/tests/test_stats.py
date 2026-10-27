from datetime import UTC, datetime

import pytest

from app.models import House, PoliticianStats
from app.services.stats import (
    attendance_rate,
    build_house_averages,
    compute_all,
    house_average,
    legislature_start_year,
    parse_period,
    unjustified_absences,
)


def test_attendance_rate():
    assert attendance_rate(3, 4) == 75.0
    assert attendance_rate(0, 0) is None
    assert attendance_rate(2, 3) == 66.67


def test_justified_never_counted_as_absence():
    # 10 sessões, 7 presenças, 2 justificadas → 1 falta
    assert unjustified_absences(10, 7, 2) == 1
    assert unjustified_absences(3, 3, 0) == 0
    assert unjustified_absences(3, 2, 5) == 0  # nunca negativo


def test_house_average_ignores_missing():
    assert house_average([10, None, 20]) == 15.0
    assert house_average([None]) is None


def test_house_averages_are_per_house():
    rows = [
        {"house": House.camara, "attendance_rate": 80, "votes_participated": 10,
         "bills_authored": 2, "expenses_total": 100},
        {"house": House.camara, "attendance_rate": 60, "votes_participated": 20,
         "bills_authored": 0, "expenses_total": 300},
        {"house": House.senado, "attendance_rate": 90, "votes_participated": 5,
         "bills_authored": 1, "expenses_total": 50},
    ]  # fmt: skip
    avg = build_house_averages(rows)
    assert avg[House.camara]["attendance_rate"] == 70.0
    assert avg[House.camara]["expenses_total"] == 200.0
    assert avg[House.senado]["attendance_rate"] == 90.0


def test_parse_period():
    assert legislature_start_year(57) == 2023
    p = parse_period(None, 57)
    assert p.key == "leg57"
    assert p.start == datetime(2023, 2, 1, tzinfo=UTC)
    assert p.end == datetime(2027, 2, 1, tzinfo=UTC)
    y = parse_period("2026", 57)
    assert (y.start.year, y.end.year) == (2026, 2027)
    with pytest.raises(ValueError):
        parse_period("abc", 57)


async def test_compute_all(db, seed):
    n = await compute_all(db, parse_period("2026", 57))
    assert n == 3
    ana = await db.get(PoliticianStats, (seed["a"].id, "2026"))
    bruno = await db.get(PoliticianStats, (seed["b"].id, "2026"))
    assert ana.sessions_total == 4
    assert ana.sessions_present == 3
    assert ana.sessions_justified == 1
    assert float(ana.attendance_rate) == 75.0
    assert float(bruno.attendance_rate) == 50.0
    assert ana.bills_authored == 1
    assert ana.votes_participated == 1
    assert float(ana.expenses_total) == 1000.5
    # média da Câmara não inclui a senadora
    assert ana.house_avg["attendance_rate"] == 62.5


async def test_requerimentos_do_not_count_as_bills(db, seed):
    from app.models import AuthorRole, Bill, BillAuthor

    for i, tipo in enumerate(["REQ", "RPD", "DOC", "PEC"]):
        b = Bill(house=House.camara, external_id=f"x{i}", type=tipo)
        db.add(b)
        await db.flush()
        db.add(BillAuthor(bill_id=b.id, politician_id=seed["a"].id, role=AuthorRole.autor))
    await db.commit()
    await compute_all(db, parse_period("2026", 57))
    ana = await db.get(PoliticianStats, (seed["a"].id, "2026"))
    assert ana.bills_authored == 2  # o PL do seed + a PEC; requerimentos e documentos não


async def test_compute_all_is_idempotent(db, seed):
    period = parse_period("2026", 57)
    await compute_all(db, period)
    await compute_all(db, period)
    from sqlalchemy import func, select

    count = (await db.execute(select(func.count()).select_from(PoliticianStats))).scalar()
    assert count == 3

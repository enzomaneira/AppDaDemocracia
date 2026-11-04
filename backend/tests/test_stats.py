from datetime import UTC, datetime

import pytest

from app.models import House, PoliticianStats
from app.services.stats import (
    alignment_rate,
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


async def test_senado_justified_absence_and_secret_vote(db, seed):
    from datetime import UTC, datetime

    from app.models import Attendance, AttendanceStatus, Session, Vote, VoteChoice, VoteRecord

    carla = seed["c"]
    when = datetime(2026, 5, 5, 15, tzinfo=UTC)
    for i, status in enumerate(["presente", "justificada", "ausente", "presente"]):
        s = Session(house=House.senado, external_id=f"ss{i}", is_deliberative=True, starts_at=when)
        db.add(s)
        await db.flush()
        db.add(Attendance(session_id=s.id, politician_id=carla.id,
                          status=AttendanceStatus(status)))  # fmt: skip
    for i, choice in enumerate(["secreto", "presente", "justificada", "sim"]):
        v = Vote(house=House.senado, external_id=f"sv{i}", voted_at=when)
        db.add(v)
        await db.flush()
        db.add(VoteRecord(vote_id=v.id, politician_id=carla.id, choice=VoteChoice(choice)))
    await db.commit()
    await compute_all(db, parse_period("2026", 57))
    st = await db.get(PoliticianStats, (carla.id, "2026"))
    assert (st.sessions_total, st.sessions_present, st.sessions_justified) == (4, 2, 1)
    assert float(st.attendance_rate) == 50.0
    # voto secreto e "sim" contam; presente sem voto e ausência justificada, não
    assert (st.votes_participated, st.votes_total) == (2, 4)


def test_alignment_rate():
    assert alignment_rate(8, 10) == 80.0
    assert alignment_rate(0, 10) == 0.0
    assert alignment_rate(9, 9) is None  # amostra abaixo do mínimo
    assert alignment_rate(0, 0) is None


async def _add_votes(db, seed, n, *, a, b, party=None, government=None):
    """Adiciona n votações; a/b são as escolhas (VoteChoice) de Ana e Bruno."""
    from sqlalchemy import select

    from app.models import Vote, VoteRecord

    when = (await db.execute(select(Vote))).scalars().first().voted_at
    for i in range(n):
        v = Vote(
            house=House.camara,
            external_id=f"extra-{a}-{b}-{i}",
            voted_at=when,
            government_orientation=government,
        )
        db.add(v)
        await db.flush()
        for pol, choice in ((seed["a"], a), (seed["b"], b)):
            db.add(
                VoteRecord(
                    vote_id=v.id, politician_id=pol.id, choice=choice, party_orientation=party
                )
            )
    await db.commit()


async def test_party_alignment_needs_minimum_sample(db, seed):
    # seed tem 1 votação comparável: abaixo do mínimo, a taxa não é exibida (mas a contagem sim)
    await compute_all(db, parse_period("2026", 57))
    ana = await db.get(PoliticianStats, (seed["a"].id, "2026"))
    assert ana.party_alignment_rate is None and ana.party_votes_compared == 1
    assert ana.government_alignment_rate is None and ana.government_votes_compared == 0


async def test_party_alignment(db, seed):
    from app.models import VoteChoice

    # +9 votações com orientação "sim": Ana sempre Sim, Bruno sempre Não → 10 no total com o seed
    await _add_votes(db, seed, 9, a=VoteChoice.sim, b=VoteChoice.nao, party="sim")
    await compute_all(db, parse_period("2026", 57))
    ana = await db.get(PoliticianStats, (seed["a"].id, "2026"))
    bruno = await db.get(PoliticianStats, (seed["b"].id, "2026"))
    assert (float(ana.party_alignment_rate), ana.party_votes_compared) == (100.0, 10)
    assert (float(bruno.party_alignment_rate), bruno.party_votes_compared) == (0.0, 10)


async def test_government_alignment_ignores_liberado_and_non_positional_votes(db, seed):
    from app.models import VoteChoice

    # 10 votações em que o governo orienta "nao": Ana (Sim) diverge, Bruno (Não) acompanha
    await _add_votes(db, seed, 10, a=VoteChoice.sim, b=VoteChoice.nao, government="nao")
    # "liberado" e voto de abstenção não entram na comparação
    await _add_votes(db, seed, 3, a=VoteChoice.sim, b=VoteChoice.abstencao, government="liberado")
    await _add_votes(db, seed, 3, a=VoteChoice.abstencao, b=VoteChoice.abstencao, government="sim")
    await compute_all(db, parse_period("2026", 57))
    ana = await db.get(PoliticianStats, (seed["a"].id, "2026"))
    bruno = await db.get(PoliticianStats, (seed["b"].id, "2026"))
    assert (float(ana.government_alignment_rate), ana.government_votes_compared) == (0.0, 10)
    assert (float(bruno.government_alignment_rate), bruno.government_votes_compared) == (
        100.0,
        10,
    )
    assert ana.house_avg["government_alignment_rate"] == 50.0

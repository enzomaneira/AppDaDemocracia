import itertools
from decimal import Decimal

from ingestion.jobs.common import slugify
from ingestion.jobs.sync_bills import bill_label
from ingestion.jobs.sync_expenses import parse_brl
from ingestion.jobs.sync_votes import orientation_by_party, parse_identificacao, senado_result
from ingestion.sources import camara, senado
from ingestion.sources.news_rss import clean_snippet, parse_feed


def test_orientation_party_beats_federation():
    out = orientation_by_party(
        [
            {
                "orientacaoVoto": "Não",
                "codTipoLideranca": "B",
                "siglaPartidoBloco": "Fdr PT-PCdoB-PV",
            },
            {"orientacaoVoto": "Sim", "codTipoLideranca": "P", "siglaPartidoBloco": "PV"},
            {"orientacaoVoto": "Obstrução", "codTipoLideranca": "P", "siglaPartidoBloco": "PL"},
            {"orientacaoVoto": "Sim", "codTipoLideranca": "G", "siglaPartidoBloco": "Governo"},
        ]
    )
    assert out["PT"] == "nao"
    assert out["PCDOB"] == "nao"
    assert out["PV"] == "sim"  # orientação do próprio partido prevalece
    assert out["PL"] == "obstrucao"
    assert "GOVERNO" not in out


def test_labels_and_senado_result():
    from app.models import Bill

    assert bill_label(Bill(type="PL", number=10, year=2026)) == "PL 10/2026"
    assert bill_label(Bill(type="PRL", number=1, year=0)) == "PRL"
    assert senado_result("A") == "Aprovada"
    assert senado_result("Outro") == "Outro"


def test_parse_identificacao():
    assert parse_identificacao("PEC 81/2015") == ("PEC", 81, 2015)
    assert parse_identificacao("algo") == (None, None, None)


def test_vote_maps():
    assert camara.map_vote("Não") == "nao"
    assert camara.map_vote("Artigo 17") == "art17"
    assert camara.map_vote(None) == "ausente"
    # Senado: comparecimento vem no próprio registro de votação
    assert senado.map_vote("Votou") == "secreto"
    assert senado.map_vote("P-NRV") == "presente"
    assert senado.map_vote("Presidente (art. 51 RISF)") == "art17"
    for justificada in ("AP", "MIS", "LS", "LP"):
        assert senado.map_vote(justificada) == "justificada"
    assert senado.map_vote("NCom") == "ausente"
    assert senado.map_vote("NA") is None  # "dispositivo não citado": não conta


def test_plenary_deliberative():
    assert camara.is_plenary_deliberative(
        {"descricaoTipo": "Sessão Deliberativa", "orgaos": [{"sigla": "PLEN"}]}
    )
    assert not camara.is_plenary_deliberative(
        {"descricaoTipo": "Sessão Não Deliberativa Solene", "orgaos": [{"sigla": "PLEN"}]}
    )
    assert not camara.is_plenary_deliberative(
        {"descricaoTipo": "Reunião Deliberativa", "orgaos": [{"sigla": "CCJC"}]}
    )


def test_parse_brl():
    assert parse_brl("1.234,56") == Decimal("1234.56")
    assert parse_brl("99.9") == Decimal("99.9")
    assert parse_brl("") == 0


def test_senador_uf_from_mandato():
    d = senado.parse_senador(
        {
            "IdentificacaoParlamentar": {"CodigoParlamentar": 1, "NomeParlamentar": "Fulana"},
            "Mandato": {"UfParlamentar": "PE"},
        }
    )
    assert d["uf"] == "PE" and d["external_id"] == "1"


def test_slugify():
    assert slugify("José da Silva Júnior") == "jose-da-silva-junior"


def test_rss_keeps_only_short_snippet():
    long = "<p>" + "palavra " * 100 + "</p>"
    assert len(clean_snippet(long)) <= 280
    xml = b"""<?xml version="1.0"?><rss><channel><title>Agencia</title>
      <item><title>Deputada fala</title><link>https://ex.com/a</link>
      <description>&lt;b&gt;Resumo&lt;/b&gt;</description>
      <pubDate>Tue, 27 Oct 2026 10:00:00 GMT</pubDate></item></channel></rss>"""
    [item] = parse_feed(xml)
    assert item.url == "https://ex.com/a"
    assert item.snippet == "Resumo"
    assert item.source_name == "Agencia"


def test_office_periods_from_historico():
    hist = [
        {"dataHora": "2023-02-01T00:00", "situacao": None},
        {"dataHora": "2023-02-01T12:05", "situacao": "Exercício"},
        {"dataHora": "2023-02-10T00:00", "situacao": "Exercício"},  # troca de partido
        {"dataHora": "2024-03-01T00:00", "situacao": "Licença"},
        {"dataHora": "2024-07-01T00:00", "situacao": "Exercício"},
        {"dataHora": "2025-01-01T00:00", "situacao": "VACANCIA"},
    ]
    assert camara.parse_office_periods(hist) == [
        ["2023-02-01", "2024-03-01"],
        ["2024-07-01", "2025-01-01"],
    ]
    assert camara.parse_office_periods([]) == []


def test_in_exercise_respects_periods():
    from datetime import UTC, datetime

    from app.models import Politician
    from ingestion.jobs.common import in_exercise

    p = Politician(in_office=True, office_periods=[["2023-02-01", "2024-03-01"]])
    assert in_exercise(p, datetime(2023, 6, 1, tzinfo=UTC))
    assert not in_exercise(p, datetime(2024, 3, 1, tzinfo=UTC))  # fim é exclusivo
    suplente = Politician(in_office=True, office_periods=[["2025-05-10", None]])
    assert not in_exercise(suplente, datetime(2024, 1, 1, tzinfo=UTC))
    assert in_exercise(suplente, datetime(2026, 1, 1, tzinfo=UTC))
    # Sem histórico (ex.: senadores): cai para a situação atual.
    assert in_exercise(Politician(in_office=True, office_periods=None), datetime.now(UTC))


def test_date_chunks_respect_three_months():
    from datetime import date, timedelta

    from ingestion.jobs.common import date_chunks

    chunks = date_chunks(date(2023, 2, 1), date(2023, 12, 31))
    assert chunks[0][0] == date(2023, 2, 1) and chunks[-1][1] == date(2023, 12, 31)
    assert all((e - s) < timedelta(days=90) for s, e in chunks)
    assert all(b[0] == a[1] + timedelta(days=1) for a, b in itertools.pairwise(chunks))
    assert date_chunks(date(2026, 1, 2), date(2026, 1, 1)) == []


def test_sync_start_continues_or_backfills(monkeypatch):
    from datetime import UTC, date, datetime

    from app.core.config import get_settings
    from ingestion.jobs.common import sync_start

    s = get_settings()
    monkeypatch.setattr(s, "sync_since", None)
    monkeypatch.setattr(s, "sync_days_back", 3)
    # Banco vazio → início da legislatura (57ª: 01/02/2023)
    assert sync_start(None) == date(2023, 2, 1)
    # Continua do último item gravado, com folga — mesmo após semanas de recesso
    assert sync_start(datetime(2026, 10, 15, 20, tzinfo=UTC)) == date(2026, 10, 12)
    monkeypatch.setattr(s, "sync_since", date(2024, 1, 1))
    assert sync_start(datetime(2026, 10, 15, tzinfo=UTC)) == date(2024, 1, 1)


def test_backfill_does_not_flood_feed():
    from datetime import UTC, datetime, timedelta

    from ingestion.jobs.common import feed_worthy

    assert feed_worthy(datetime.now(UTC) - timedelta(days=2))
    assert not feed_worthy(datetime(2023, 5, 1, tzinfo=UTC))


def test_run_daily_args():
    from datetime import date

    from ingestion.run_daily import parse_args

    a = parse_args(["--since", "2023-02-01", "votes", "stats"])
    assert a.since == date(2023, 2, 1) and a.jobs == ["votes", "stats"]
    assert parse_args([]).jobs == []


async def test_http_does_not_retry_404_but_retries_503(monkeypatch):
    import httpx
    import pytest

    from ingestion.http import HttpClient

    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if request.url.path == "/missing":
            return httpx.Response(404)
        return httpx.Response(503) if calls["n"] < 3 else httpx.Response(200, json={"ok": 1})

    async def no_sleep(_):
        return None

    monkeypatch.setattr("ingestion.http.asyncio.sleep", no_sleep)
    client = HttpClient("http://fonte.test")
    client._client = httpx.AsyncClient(
        base_url="http://fonte.test", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(httpx.HTTPStatusError):
        await client.get("/missing")
    assert calls["n"] == 1  # 404: sem nova tentativa
    calls["n"] = 0
    assert (await client.get_json("/flaky")) == {"ok": 1}
    assert calls["n"] == 3  # 503, 503, 200
    await client.aclose()


def test_sync_jobs_env(monkeypatch):
    import subprocess
    import sys

    r = subprocess.run(
        [
            sys.executable,
            "-c",
            "import runpy; runpy.run_module('ingestion.run_daily', run_name='__main__')",
        ],
        env={**__import__("os").environ, "SYNC_JOBS": "votes,nao-existe"},
        capture_output=True,
        text=True,
    )
    assert r.returncode != 0 and "nao-existe" in r.stderr


def test_expense_keys_keep_repeated_source_ids():
    from ingestion.jobs.sync_expenses import keyed_rows

    rows = [
        {"ideDocumento": "0", "numMes": "10", "vlrLiquido": "107.29"},
        {"ideDocumento": "0", "numMes": "11", "vlrLiquido": "107.29"},
        {"ideDocumento": "142935", "numMes": "3", "vlrLiquido": "500.68"},
        {"ideDocumento": "142935", "numMes": "3", "vlrLiquido": "-32.86"},  # estorno
        {"ideDocumento": "142935", "numMes": "3", "vlrLiquido": "-32.86"},  # linha idêntica
    ]
    keys = [k for k, _ in keyed_rows(rows, "camara", 2023)]
    assert len(set(keys)) == 5  # nenhuma linha some
    assert all(k.startswith("camara:2023:") for k in keys)
    # Estável entre execuções (mesmo arquivo → mesmas chaves)
    assert keys == [k for k, _ in keyed_rows(rows, "camara", 2023)]


async def test_expense_year_replace_is_idempotent(db, seed):
    from decimal import Decimal

    from sqlalchemy import func, select

    from app.models import Expense, House
    from ingestion.jobs.common import politician_index
    from ingestion.jobs.sync_expenses import _camara_year

    rows = [
        {"ideCadastro": "1", "ideDocumento": "0", "numMes": "1", "vlrLiquido": "100.00",
         "txtDescricao": "TELEFONIA"},
        {"ideCadastro": "1", "ideDocumento": "0", "numMes": "2", "vlrLiquido": "50.50",
         "txtDescricao": "TELEFONIA"},
        {"ideCadastro": "2", "ideDocumento": "9", "numMes": "1", "vlrLiquido": "10.00",
         "txtDescricao": "TAXI"},
    ]  # fmt: skip

    class FakeApi:
        async def ceap_csv(self, year):
            return rows

    pols = await politician_index(db, House.camara)
    total = select(func.sum(Expense.amount)).where(Expense.year == 2026)
    for _ in range(2):  # roda duas vezes: substitui, não duplica
        assert await _camara_year(db, FakeApi(), pols, 2026) == 3
        # o lançamento do seed (1000.50, 2026) foi substituído pelo conteúdo do arquivo
        assert (await db.execute(total)).scalar() == Decimal("160.50")


def test_senado_session_attendance():
    from ingestion.sources.senado import session_attendance

    assert session_attendance(["secreto", "justificada"]) == "presente"  # presente em uma
    assert session_attendance(["presente"]) == "presente"
    assert session_attendance(["justificada", "justificada"]) == "justificada"
    assert session_attendance(["ausente", "justificada"]) == "justificada"
    assert session_attendance(["ausente"]) == "ausente"
    assert session_attendance([]) is None


def test_parse_processo():
    from ingestion.sources.senado import parse_processo

    assert parse_processo(
        {"identificacao": "PL 2036/2023", "codigoMateria": 157013, "ementa": "Segurança escolar"}
    ) == {
        "external_id": "157013",
        "type": "PL",
        "number": 2036,
        "year": 2023,
        "official_summary": "Segurança escolar",
    }
    assert parse_processo({"identificacao": "RQS 41/2023", "codigoMateria": 1})["type"] == "RQS"
    assert parse_processo({"identificacao": "Ofício", "codigoMateria": 1}) is None


async def test_senado_roster_is_authoritative(db, seed):
    """No Senado, quem não está na lista da votação não estava em exercício: não é falta."""
    from datetime import UTC, datetime

    from sqlalchemy import select

    from app.models import House, Politician, Vote, VoteRecord
    from ingestion.jobs.common import politician_index
    from ingestion.jobs.sync_votes import _save_vote

    db.add(Politician(house=House.senado, external_id="77", civil_name="Suplente",
                      parliamentary_name="Suplente", slug="suplente-mg", uf="MG"))  # fmt: skip
    await db.commit()
    pols = await politician_index(db, House.senado)
    when = datetime(2026, 5, 5, tzinfo=UTC)
    args = (db, House.senado, "sv1", when, "Votação", "Aprovada", None)

    # Versão antiga preenchia o suplente como ausente; a nova remove esse registro.
    await _save_vote(*args, {"9": ("sim", None), "77": ("ausente", None)}, pols)
    await _save_vote(*args, {"9": ("sim", None)}, pols, {"9"})
    await db.commit()
    q = select(VoteRecord).join(Vote).where(Vote.external_id == "sv1")
    recs = (await db.execute(q)).scalars().all()
    assert [(r.politician_id, r.choice.value) for r in recs] == [(pols["9"].id, "sim")]

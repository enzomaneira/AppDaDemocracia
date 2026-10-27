from decimal import Decimal

from ingestion.jobs.common import slugify
from ingestion.jobs.sync_bills import author_role, bill_label
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


def test_parecer_counts_as_relatoria():
    from app.models import AuthorRole, Bill

    assert author_role("PRL") == AuthorRole.relator
    assert author_role("PL") == AuthorRole.autor
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
    assert senado.map_vote("Sim") == "sim"
    assert senado.map_vote("AP") == "ausente"


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

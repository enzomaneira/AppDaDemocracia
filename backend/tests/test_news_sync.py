import uuid
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse

from app.services.news_matching import (
    QUERY_CONF_NAME_IN_TITLE,
    Candidate,
    is_listing_noise,
    query_confidence,
)
from ingestion.jobs.sync_news import collect
from ingestion.sources.news_rss import RssItem, google_news_url, parse_feed

MARA = Candidate(uuid.uuid4(), "Mara Gabrilli", "Mara Cristina Gabrilli", "senado", "PSD", "SP")
ALAN = Candidate(uuid.uuid4(), "Alan Rick", "Alan Rick Miranda", "senado", "REPUBLICANOS", "AC")


def item(title, url=None):
    return RssItem(
        url=url or f"https://n.test/{abs(hash(title))}",
        title=title,
        snippet=None,
        source_name="Veículo",
        published_at=datetime.now(UTC),
        image_url=None,
    )


def test_listing_noise_only_for_candidate_pages():
    assert is_listing_noise("Mara Gabrilli 55177 (PSD): candidata a Deputado Estadual pelo SP")
    assert is_listing_noise("Fulano 123 (UNIÃO BRASIL): candidato a senador")
    # notícia legítima sobre candidatura, e números comuns em notícia, não são ruído
    assert not is_listing_noise("Mara Gabrilli é candidata a governadora de SP")
    assert not is_listing_noise("PEC 45 (reforma tributária) avança no Senado")
    assert not is_listing_noise("Lei 14.301 (2022) é prorrogada")


def test_query_confidence_reflects_what_title_shows():
    # nome + contexto no título: regra geral
    assert query_confidence("Senadora Mara Gabrilli (PSD-SP) apresenta projeto", MARA) >= 0.8
    # só o nome no título (o cargo estava no texto, pela busca)
    assert (
        query_confidence("Mara Gabrilli defende acessibilidade", MARA) == QUERY_CONF_NAME_IN_TITLE
    )
    # nome só no corpo da matéria: não vincula (o título não mostraria o porquê)
    assert query_confidence("Projeto prevê material em braile", MARA) is None


def test_collect_merges_urls_and_filters_noise():
    shared = item(
        "Alan Rick e Mara Gabrilli divergem sobre PEC; senadores (AC e SP)", "https://n.test/x"
    )
    found = collect(
        general=[item("Agência: senadora Mara Gabrilli (PSD) visita escola", "https://n.test/ag")],
        per_politician=[
            (MARA, [shared, item("Mara Gabrilli 55177 (PSD): candidata a Deputado Estadual"),
                    item("Projeto prevê material em braile", "https://n.test/b")]),
            (ALAN, [shared]),
        ],
        candidates=[MARA, ALAN],
    )  # fmt: skip
    assert set(found) == {"https://n.test/ag", "https://n.test/x"}  # sem a de só-corpo
    # mesma URL vinda de duas buscas = uma notícia, com os dois parlamentares
    assert set(found["https://n.test/x"].mentions) == {MARA.politician_id, ALAN.politician_id}


def test_collect_general_feed_keeps_strict_rule():
    found = collect([item("Mara Gabrilli abre padaria")], [], [MARA])
    assert found == {}  # agência sem contexto: não vincula


def test_google_news_url_requires_name_and_role():
    q = parse_qs(urlparse(google_news_url("Mara Gabrilli", "senado", "30d")).query)["q"][0]
    assert q == '"Mara Gabrilli" (senador OR senadora) when:30d'
    q = parse_qs(urlparse(google_news_url("Tabata Amaral", "camara", "2d")).query)["q"][0]
    assert q == '"Tabata Amaral" (deputado OR deputada) when:2d'


def test_parse_feed_cleans_google_news_items():
    xml = b"""<?xml version="1.0"?><rss><channel><title>Google News</title>
      <item><title>Mara Gabrilli defende acessibilidade - Folha</title>
      <link>https://news.google.com/rss/articles/abc</link>
      <description>&lt;a href="x"&gt;Mara Gabrilli defende acessibilidade&lt;/a&gt;
      Folha</description>
      <source url="https://folha.uol.com.br">Folha</source>
      <pubDate>Tue, 27 Oct 2026 10:00:00 GMT</pubDate></item></channel></rss>"""
    [it] = parse_feed(xml)
    assert it.title == "Mara Gabrilli defende acessibilidade"  # sem " - Folha"
    assert it.source_name == "Folha"
    assert it.snippet is None  # resumo do Google só repete o título


VERMELHO = Candidate(uuid.uuid4(), "Vermelho", "Fulano de Tal", "camara", "PL", "PR")


def test_single_word_name_needs_name_and_context_in_title():
    found = collect(
        general=[],
        per_politician=[
            (VERMELHO, [
                item("Juscelino Filho fala sobre a bandeira vermelha", "https://n.test/v1"),
                item("Projeto do Congresso entra em alerta", "https://n.test/v2"),  # só no corpo
                item("Deputado Vermelho (PL-PR) apresenta projeto", "https://n.test/v3"),
            ]),
        ],
        candidates=[VERMELHO],
    )  # fmt: skip
    assert set(found) == {"https://n.test/v3"}


def test_more_candidate_page_formats_are_noise():
    assert is_listing_noise("Dr° Damião 4444 (UNIÃO), candidato a Deputado Federal da PB em 2026")
    assert is_listing_noise(
        "Juscelino Filho Candidato a Deputado Federal no Maranhão nas eleições 2026"
    )
    assert not is_listing_noise("Juscelino Filho é candidato a governador e lança plano de governo")


def test_single_word_name_glued_to_another_name_is_a_homonym():
    from app.services.news_matching import part_of_other_name

    cleitinho = Candidate(uuid.uuid4(), "Cleitinho", "Cleiton Gontijo de Azevedo", "senado",
                          "REPUBLICANOS", "MG")  # fmt: skip
    assert part_of_other_name("Matheus Vermelho (PL) é eleito deputado estadual", VERMELHO)
    assert not part_of_other_name("Vermelho (PL) é eleito deputado federal pelo Paraná", VERMELHO)
    assert not part_of_other_name("Deputado Vermelho apresenta projeto", VERMELHO)
    assert not part_of_other_name("Entrevista com Vermelho, deputado do PL", VERMELHO)
    # sobrenome do próprio parlamentar não é outro nome
    assert not part_of_other_name("O senador Cleitinho Azevedo se manifestou", cleitinho)
    # título todo em maiúsculas: nome longo continua sendo nome, sigla curta não
    assert part_of_other_name("MATHEUS VERMELHO é eleito deputado estadual no Paraná", VERMELHO)
    assert not part_of_other_name("VERMELHO (PL) é eleito deputado federal", VERMELHO)


def test_election_listing_pages_are_noise():
    assert is_listing_noise(
        "Apuração ao vivo dos votos em Ibirapitanga (BA) nas Eleições 2026 | Veja quem são os"
    )
    assert is_listing_noise("Lista de quem são todos os candidatos ao Senado por Sergipe (SE)")
    assert not is_listing_noise("Veja quem são os 53 deputados federais eleitos por Minas Gerais")
    assert is_listing_noise(
        "Candidatos ao Senado pelo Ceará (CE): veja quais são os nomes e números"
    )
    assert is_listing_noise("Vermelho (PL): candidato a Deputado Federal")
    assert is_listing_noise("Gutemberg Reis: candidato a Deputado Federal")
    assert is_listing_noise("Eleições 2026")
    assert not is_listing_noise(
        "Eleições 2026: Vermelho (PL) é eleito deputado federal pelo Paraná"
    )

import uuid

from app.services.news_matching import MIN_CONFIDENCE, Candidate, match_article, normalize, score

ANA = Candidate(uuid.uuid4(), "Ana Souza", "Ana Maria Souza", "camara", "PA", "SP")
TIRIRICA = Candidate(uuid.uuid4(), "Tiririca", "Francisco Everardo", "camara", "PL", "SP")


def test_normalize_removes_accents():
    assert normalize("  São   PAULO  ") == "sao paulo"


def test_name_without_context_is_rejected():
    assert score("Ana Souza abriu uma padaria no bairro", ANA) == 0


def test_name_with_role_context_matches():
    assert score("A deputada Ana Souza apresentou projeto", ANA) >= 0.6


def test_party_or_uf_context_matches():
    assert score("Ana Souza (PA) critica proposta", ANA) >= 0.6
    assert score("Ana Souza, de São Paulo, critica proposta", ANA) >= 0.6


def test_more_context_raises_confidence():
    low = score("deputada Ana Souza fala", ANA)
    high = score("A deputada Ana Souza (PA-SP) fala", ANA)
    assert high > low


def test_civil_name_counts():
    assert score("Ana Maria Souza, deputada, votou", ANA) > score("Ana Souza, deputada, votou", ANA)


def test_partial_word_does_not_match():
    assert score("deputada Ana Souzaneto falou", ANA) == 0


def test_single_word_name_needs_more_context():
    assert score("Tiririca, deputado, comenta", TIRIRICA) < MIN_CONFIDENCE
    assert match_article("Tiririca, deputado, comenta", [TIRIRICA]) == []
    assert score("O deputado Tiririca (PL-SP) comenta", TIRIRICA) >= MIN_CONFIDENCE


def test_match_article_returns_only_matches():
    out = match_article("deputada Ana Souza", [ANA, TIRIRICA])
    assert [m.politician_id for m in out] == [ANA.politician_id]

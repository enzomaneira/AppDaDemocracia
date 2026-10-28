"""Vínculo notícia → político.

Regra de negócio: a notícia só é vinculada quando o nome completo ou o nome parlamentar
aparece no texto E o contexto bate (cargo, partido ou UF), para evitar homônimos.
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from dataclasses import dataclass, field

UF_NAMES = {
    "AC": "acre", "AL": "alagoas", "AP": "amapa", "AM": "amazonas", "BA": "bahia",
    "CE": "ceara", "DF": "distrito federal", "ES": "espirito santo", "GO": "goias",
    "MA": "maranhao", "MT": "mato grosso", "MS": "mato grosso do sul", "MG": "minas gerais",
    "PA": "para", "PB": "paraiba", "PR": "parana", "PE": "pernambuco", "PI": "piaui",
    "RJ": "rio de janeiro", "RN": "rio grande do norte", "RS": "rio grande do sul",
    "RO": "rondonia", "RR": "roraima", "SC": "santa catarina", "SP": "sao paulo",
    "SE": "sergipe", "TO": "tocantins",
}  # fmt: skip

ROLE_WORDS = {
    "camara": ["deputado", "deputada", "parlamentar", "camara"],
    "senado": ["senador", "senadora", "parlamentar", "senado"],
}

MIN_CONFIDENCE = 0.6


def normalize(text: str) -> str:
    """Minúsculas, sem acentos e com espaços simples."""
    nfkd = unicodedata.normalize("NFKD", text)
    no_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", no_accents.lower()).strip()


def _has_word(haystack: str, needle: str) -> bool:
    if not needle:
        return False
    return re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", haystack) is not None


@dataclass
class Candidate:
    politician_id: uuid.UUID
    parliamentary_name: str
    civil_name: str
    house: str
    party: str | None
    uf: str
    _norm: dict[str, str] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        self._norm = {
            "parl": normalize(self.parliamentary_name),
            "civil": normalize(self.civil_name),
            "party": normalize(self.party or ""),
            "uf": self.uf.lower(),
            "uf_name": UF_NAMES.get(self.uf.upper(), ""),
        }


@dataclass
class Match:
    politician_id: uuid.UUID
    confidence: float


def score(text: str, c: Candidate) -> float:
    """0 quando a regra não é cumprida; caso contrário, confiança entre 0.6 e 1.0."""
    return _score_normalized(normalize(text), c)


def _score_normalized(t: str, c: Candidate) -> float:
    n = c._norm
    # Filtro barato antes das regex: sem o nome como substring, não há o que conferir.
    if n["parl"] not in t and n["civil"] not in t:
        return 0.0
    civil_hit = len(n["civil"].split()) >= 2 and _has_word(t, n["civil"])
    parl_hit = _has_word(t, n["parl"])
    if not (civil_hit or parl_hit):
        return 0.0

    role_hit = any(_has_word(t, w) for w in ROLE_WORDS.get(c.house, []))
    party_hit = _has_word(t, n["party"])
    uf_hit = _has_word(t, n["uf"]) or _has_word(t, n["uf_name"])
    context_hits = sum([role_hit, party_hit, uf_hit])
    if context_hits == 0:
        return 0.0

    conf = 0.5 + 0.15 * context_hits + (0.1 if civil_hit else 0.0)
    # Nome parlamentar de uma palavra só é mais ambíguo.
    if not civil_hit and len(n["parl"].split()) == 1:
        conf -= 0.1
    return round(min(conf, 1.0), 2)


def match_article(text: str, candidates: list[Candidate]) -> list[Match]:
    t = normalize(text)  # uma vez por texto, não uma vez por candidato
    out = []
    for c in candidates:
        s = _score_normalized(t, c)
        if s >= MIN_CONFIDENCE:
            out.append(Match(c.politician_id, s))
    return out


# Páginas de candidatura/resultado ("Fulana 55177 (PSD): candidata a ...") são listagens
# eleitorais, não notícias, e costumam ser de homônimos candidatos a outros cargos. O que as
# identifica é o número de urna seguido do partido; "candidata a" sozinho é notícia legítima.
_CANDIDATE_NUMBER = re.compile(r"\b\d{2,5}\s*\([A-ZÀ-Ú][A-ZÀ-Ú ]*\)\s*[:,–-]")
# Páginas de perfil de candidato ("Fulano Candidato a Deputado Federal no MA nas eleições 2026").
_CANDIDATE_PROFILE = re.compile(r"\bcandidat[oa] a .{3,80} nas eleicoes \d{4}\s*$")


# Páginas automáticas de apuração por município e listas de todos os candidatos.
_ELECTION_LISTING = re.compile(
    r"^apuracao (ao vivo )?dos votos|\bcandidatos mais votados\b|^lista de quem sao (todos )?os"
    r"|\bveja (quais|quem) sao os (nomes|candidatos)"
    # perfil de candidatura: "Fulano (PL): candidato a Deputado Federal", e mais nada
    r"|^[^:]{2,80}:\s*candidat[oa]s? a [a-z ]+$"
    # título que é só o nome da cobertura ("Eleições 2026")
    r"|^eleicoes \d{4}$"
)


def is_listing_noise(title: str) -> bool:
    t = normalize(title)
    return bool(
        _CANDIDATE_NUMBER.search(title)
        or _CANDIDATE_PROFILE.search(t)
        or _ELECTION_LISTING.search(t)
    )


# Palavras que podem vir coladas ao nome sem fazer parte dele ("Deputado Vermelho").
_HONORIFICS = {
    "deputado", "deputada", "dep", "senador", "senadora", "sen", "o", "a", "do", "da", "de",
    "ex", "líder", "lider", "presidente", "relator", "relatora", "parlamentar",
}  # fmt: skip
_TOKEN = re.compile(r"[\wÀ-ú]+")


def part_of_other_name(title: str, c: Candidate) -> bool:
    """O nome de uma palavra aparece colado a outro nome próprio ("Matheus Vermelho")?

    Se toda ocorrência do nome no título vem junto de outra palavra capitalizada (que não seja
    cargo/tratamento), é outra pessoa com o mesmo sobrenome ou apelido.
    """
    tokens = _TOKEN.findall(title)
    target = c._norm["parl"]
    own = set(c._norm["civil"].split())  # "Cleitinho Azevedo": Azevedo é do próprio senador
    hits = [i for i, tok in enumerate(tokens) if normalize(tok) == target]
    if not hits:
        return False

    def is_name(i: int) -> bool:
        if not 0 <= i < len(tokens):
            return False
        tok = tokens[i]
        n = normalize(tok)
        return (
            tok[:1].isupper()
            # siglas ("Vermelho (PL)", "PR", "PSDB"); em título todo em maiúsculas,
            # palavras longas ainda são nomes ("MATHEUS VERMELHO")
            and not (tok.isupper() and len(tok) <= 4)
            and n not in _HONORIFICS
            and n not in own
        )

    return all(is_name(i - 1) or is_name(i + 1) for i in hits)


def single_word_name(c: Candidate) -> bool:
    """Nome parlamentar de uma palavra ("Vermelho", "Albuquerque") é ambíguo demais para
    confiar só na busca: o Google casa qualquer texto com a palavra e o cargo."""
    return len(c._norm["parl"].split()) == 1


def name_in_text(text: str, c: Candidate) -> bool:
    t = normalize(text)
    civil = c._norm["civil"]
    return _has_word(t, c._norm["parl"]) or (len(civil.split()) >= 2 and _has_word(t, civil))


# Busca por parlamentar no Google News: a consulta exige o nome exato E o cargo no texto da
# matéria, então a regra "nome + contexto" é cumprida pelo texto completo. Ainda assim só
# vinculamos quando o nome aparece no TÍTULO: quem abre o perfil precisa ver por que a notícia
# está ali (rastreabilidade). Matérias que só citam o parlamentar no corpo ficam de fora.
QUERY_CONF_NAME_IN_TITLE = 0.7


def query_confidence(title: str, c: Candidate) -> float | None:
    """Confiança do vínculo vindo da busca por parlamentar; None se o nome não está no título."""
    s = score(title, c)
    if s >= MIN_CONFIDENCE:
        return max(s, QUERY_CONF_NAME_IN_TITLE)
    if name_in_text(title, c):
        return QUERY_CONF_NAME_IN_TITLE
    return None

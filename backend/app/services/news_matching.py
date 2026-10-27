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
    t = normalize(text)
    n = c._norm
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
    out = []
    for c in candidates:
        s = score(text, c)
        if s >= MIN_CONFIDENCE:
            out.append(Match(c.politician_id, s))
    return out

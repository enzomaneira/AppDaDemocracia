"""6 · Notícias de todos os parlamentares em exercício, vinculadas com proteção a homônimos.

Duas fontes:
- RSS das agências da Câmara e do Senado: a notícia é vinculada a quem tiver nome + contexto
  (cargo, partido ou UF) no título/resumo (regra geral de news_matching).
- Google News, uma busca por parlamentar: nome exato + cargo no texto da matéria, e o nome
  precisa aparecer no título. Nome de uma palavra ("Vermelho") exige também o contexto no
  título e não pode estar colado a outro nome ("Matheus Vermelho"). Páginas de candidatura,
  apuração e listas eleitorais são descartadas.

Na primeira busca de cada parlamentar a janela é de 30 dias; depois, só os últimos dias.
Guardamos só título, fonte, data e link (sem copiar a matéria). URLs repetidas viram uma
notícia só, com todos os parlamentares citados.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import FeedType, NewsArticle, NewsMention, Politician
from app.services.feed import add_event
from app.services.news_matching import (
    MIN_CONFIDENCE,
    Candidate,
    is_listing_noise,
    match_article,
    part_of_other_name,
    query_confidence,
    score,
    single_word_name,
)
from ingestion.http import HttpClient
from ingestion.jobs.common import feed_worthy, tracked
from ingestion.sources import news_rss

log = logging.getLogger("ingestion.news")
FIRST_WINDOW, DAILY_WINDOW = "30d", "2d"
CHUNK = 500


@dataclass
class Found:
    item: news_rss.RssItem
    mentions: dict[uuid.UUID, float] = field(default_factory=dict)

    def add(self, pid: uuid.UUID, conf: float) -> None:
        self.mentions[pid] = max(conf, self.mentions.get(pid, 0.0))


def collect(
    general: list[news_rss.RssItem],
    per_politician: list[tuple[Candidate, list[news_rss.RssItem]]],
    candidates: list[Candidate],
) -> dict[str, Found]:
    """URL → notícia + {parlamentar: confiança}. Função pura, testável sem rede nem banco."""
    found: dict[str, Found] = {}

    def entry(item: news_rss.RssItem) -> Found:
        return found.setdefault(item.url, Found(item))

    for item in general:
        for m in match_article(f"{item.title}. {item.snippet or ''}", candidates):
            entry(item).add(m.politician_id, m.confidence)
    for cand, items in per_politician:
        for item in items:
            if is_listing_noise(item.title):
                continue
            if single_word_name(cand):
                # Nome de uma palavra: só com nome E contexto visíveis no título (regra estrita).
                conf = score(item.title, cand)
                if conf < MIN_CONFIDENCE or part_of_other_name(item.title, cand):
                    continue
            else:
                conf = query_confidence(item.title, cand)
                if conf is None:
                    continue  # nome só no corpo da matéria: o título não mostraria o porquê
            e = entry(item)
            e.add(cand.politician_id, conf)
            # Outros parlamentares citados no título também ganham o vínculo (regra geral).
            for m in match_article(item.title, candidates):
                e.add(m.politician_id, m.confidence)
    return {url: f for url, f in found.items() if f.mentions}


async def run() -> None:
    async with tracked("sync_news", "rss") as run_, SessionLocal() as db:
        pols = list(
            (await db.execute(select(Politician).where(Politician.in_office.is_(True)))).scalars()
        )
        candidates = [
            Candidate(p.id, p.parliamentary_name, p.civil_name, p.house.value,
                      p.party.acronym if p.party else None, p.uf)
            for p in pols
        ]  # fmt: skip
        with_news = set((await db.execute(select(NewsMention.politician_id).distinct())).scalars())

        async with HttpClient() as client:

            async def safe_fetch(url: str) -> list[news_rss.RssItem]:
                try:
                    return await news_rss.fetch(client, url)
                except Exception as e:  # noqa: BLE001 — uma fonte fora não derruba as demais
                    log.warning("feed falhou %s: %s", url, e)
                    return []

            async def per_pol(c: Candidate) -> tuple[Candidate, list[news_rss.RssItem]]:
                when = DAILY_WINDOW if c.politician_id in with_news else FIRST_WINDOW
                return c, await safe_fetch(
                    news_rss.google_news_url(c.parliamentary_name, c.house, when)
                )

            general_batches, per_politician = await asyncio.gather(
                asyncio.gather(*(safe_fetch(u) for u in get_settings().news_feeds)),
                asyncio.gather(*(per_pol(c) for c in candidates)),
            )

        found = collect([i for b in general_batches for i in b], per_politician, candidates)
        run_.items += await _save(db, found)


async def _save(db, found: dict[str, Found]) -> int:
    """Grava em lote: notícias novas, vínculos que faltam e itens de feed recentes."""
    urls = list(found)
    known: dict[str, uuid.UUID] = {}
    for i in range(0, len(urls), CHUNK):
        rows = await db.execute(
            select(NewsArticle.url, NewsArticle.id).where(NewsArticle.url.in_(urls[i : i + CHUNK]))
        )
        known.update(rows.all())
    linked: set[tuple[uuid.UUID, uuid.UUID]] = set()
    ids = list(known.values())
    for i in range(0, len(ids), CHUNK):
        rows = await db.execute(
            select(NewsMention.article_id, NewsMention.politician_id).where(
                NewsMention.article_id.in_(ids[i : i + CHUNK])
            )
        )
        linked.update(rows.all())

    new_links = 0
    for n, (url, f) in enumerate(found.items(), 1):
        art_id = known.get(url)
        if art_id is None:
            it = f.item
            art = NewsArticle(
                id=uuid.uuid4(), url=url, title=it.title, snippet=it.snippet,
                source_name=it.source_name, published_at=it.published_at, image_url=it.image_url,
            )  # fmt: skip
            db.add(art)
            art_id = known[url] = art.id
        for pid, conf in f.mentions.items():
            if (art_id, pid) in linked:
                continue
            linked.add((art_id, pid))
            db.add(NewsMention(article_id=art_id, politician_id=pid, confidence=conf))
            new_links += 1
            if feed_worthy(f.item.published_at):
                await add_event(
                    db, pid, FeedType.news, art_id, f.item.published_at,
                    {"title": f.item.title[:300], "source": f.item.source_name, "url": url},
                )  # fmt: skip
        if n % CHUNK == 0:
            await db.commit()
    await db.commit()
    return new_links

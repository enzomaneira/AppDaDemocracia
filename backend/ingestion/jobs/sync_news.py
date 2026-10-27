"""6 · Lê RSS das últimas 24 h, vincula notícia a político e descarta duplicadas por URL."""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import FeedType, Follow, NewsArticle, NewsMention, Politician
from app.services.feed import add_event
from app.services.news_matching import Candidate, match_article
from ingestion.http import HttpClient
from ingestion.jobs.common import tracked
from ingestion.sources import news_rss

log = logging.getLogger("ingestion.news")


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
        # Google News só para quem tem seguidores, para não disparar ~600 buscas por dia.
        followed = set((await db.execute(select(Follow.politician_id).distinct())).scalars())
        urls = list(get_settings().news_feeds) + [
            news_rss.google_news_url(p.parliamentary_name) for p in pols if p.id in followed
        ]

        async with HttpClient() as client:

            async def safe_fetch(url: str):
                try:
                    return await news_rss.fetch(client, url)
                except Exception as e:  # noqa: BLE001 — uma fonte fora não derruba as demais
                    log.warning("feed falhou %s: %s", url, e)
                    return []

            batches = await asyncio.gather(*(safe_fetch(u) for u in urls))

        seen: set[str] = set()
        for item in (i for batch in batches for i in batch):
            if item.url in seen:
                continue
            seen.add(item.url)
            matches = match_article(f"{item.title}. {item.snippet or ''}", candidates)
            if not matches:
                continue
            exists = (
                await db.execute(select(NewsArticle.id).where(NewsArticle.url == item.url))
            ).first()
            if exists:
                continue
            art = NewsArticle(
                url=item.url, title=item.title, snippet=item.snippet,
                source_name=item.source_name, published_at=item.published_at,
                image_url=item.image_url,
            )  # fmt: skip
            db.add(art)
            await db.flush()
            for m in matches:
                db.add(NewsMention(article_id=art.id, politician_id=m.politician_id,
                                   confidence=m.confidence))  # fmt: skip
                await add_event(
                    db, m.politician_id, FeedType.news, art.id, item.published_at,
                    {"title": item.title[:300], "source": item.source_name, "url": item.url},
                )  # fmt: skip
            run_.items += 1
        await db.commit()

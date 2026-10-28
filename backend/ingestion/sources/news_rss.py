"""Notícias via RSS (Google News por nome do político + agências da Câmara e do Senado).

Guarda só título, trecho curto, fonte e link — nunca a matéria inteira (direitos autorais).
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from time import mktime
from urllib.parse import quote_plus

import feedparser

from ingestion.http import HttpClient

SNIPPET_MAX = 280


@dataclass
class RssItem:
    url: str
    title: str
    snippet: str | None
    source_name: str | None
    published_at: datetime
    image_url: str | None


ROLE_QUERY = {"camara": "(deputado OR deputada)", "senado": "(senador OR senadora)"}


def google_news_url(name: str, house: str | None = None, when: str = "1d") -> str:
    """Busca no Google News pelo nome exato e, se informada a casa, pelo cargo no texto."""
    terms = f'"{name}" {ROLE_QUERY.get(house or "", "")} when:{when}'
    q = quote_plus(" ".join(terms.split()))
    return f"https://news.google.com/rss/search?q={q}&hl=pt-BR&gl=BR&ceid=BR:pt-419"


def clean_snippet(raw: str | None) -> str | None:
    if not raw:
        return None
    text = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > SNIPPET_MAX:
        text = text[: SNIPPET_MAX - 1].rsplit(" ", 1)[0] + "…"
    return text or None


def parse_feed(content: bytes, default_source: str | None = None) -> list[RssItem]:
    feed = feedparser.parse(content)
    source_title = default_source or feed.feed.get("title")
    out = []
    for e in feed.entries:
        link = e.get("link")
        if not link:
            continue
        ts = e.get("published_parsed") or e.get("updated_parsed")
        published = datetime.fromtimestamp(mktime(ts), UTC) if ts else datetime.now(UTC)
        source = e.get("source", {}).get("title") if e.get("source") else None
        image = None
        for m in e.get("media_content", []) or []:
            image = m.get("url")
            break
        title = html.unescape(e.get("title", "")).strip()
        name = source or source_title
        # Google News acrescenta " - Veículo" ao título e repete o título no resumo.
        if name and title.endswith(f" - {name}"):
            title = title[: -len(name) - 3].rstrip()
        snippet = clean_snippet(e.get("summary"))
        if snippet and snippet.startswith(title[:40]):
            snippet = None
        out.append(
            RssItem(
                url=link,
                title=title,
                snippet=snippet,
                source_name=source or source_title,
                published_at=published,
                image_url=image,
            )
        )
    return out


async def fetch(client: HttpClient, url: str, default_source: str | None = None) -> list[RssItem]:
    r = await client.get(url, retries=2)
    return parse_feed(r.content, default_source)

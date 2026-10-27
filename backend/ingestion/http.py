"""Cliente HTTP compartilhado: retry com backoff exponencial e limite de concorrência."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.core.config import get_settings

log = logging.getLogger("ingestion.http")
RETRY_STATUS = {429, 500, 502, 503, 504}


class HttpClient:
    def __init__(self, base_url: str = "", headers: dict[str, str] | None = None) -> None:
        s = get_settings()
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"User-Agent": "AppDaDemocracia/0.1 (+dados abertos)", **(headers or {})},
            timeout=httpx.Timeout(30, connect=10),
            follow_redirects=True,
        )
        self._sem = asyncio.Semaphore(s.http_concurrency)

    async def get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        retries: int = 4,
        headers: dict[str, str] | None = None,
    ):
        delay = 1.0
        for attempt in range(retries + 1):
            try:
                async with self._sem:
                    r = await self._client.get(url, params=params, headers=headers)
                if r.status_code in RETRY_STATUS and attempt < retries:
                    raise httpx.HTTPStatusError("retry", request=r.request, response=r)
                r.raise_for_status()
                return r
            except (httpx.TransportError, httpx.HTTPStatusError) as e:
                if attempt >= retries:
                    raise
                log.warning("retry %s (%s): %s", url, attempt + 1, e)
                await asyncio.sleep(delay)
                delay *= 2
        raise RuntimeError("unreachable")

    async def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        return (await self.get(url, params)).json()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> HttpClient:
        return self

    async def __aexit__(self, *exc) -> None:
        await self.aclose()

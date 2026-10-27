"""1 · Cadastro, partido, foto e situação do mandato de deputados e senadores."""

from __future__ import annotations

import asyncio

from sqlalchemy import update

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import House, Politician
from ingestion.jobs.common import party_id, politician_index, tracked, unique_slug, upsert
from ingestion.sources.camara import CamaraSource, parse_office_periods
from ingestion.sources.senado import SenadoSource, parse_senador


async def sync_camara(camara: CamaraSource) -> None:
    s = get_settings()
    async with tracked("sync_politicians", "camara") as run, SessionLocal() as db:
        ids: list[int] = []
        async for d in camara.deputados(s.legislature):
            # A lista da legislatura repete o deputado a cada mudança de partido/situação.
            if d["id"] not in ids:
                ids.append(d["id"])
            if s.sync_limit and len(ids) >= s.sync_limit:
                break
        details = await asyncio.gather(*(camara.deputado(i) for i in ids))
        historicos = await asyncio.gather(*(camara.historico(i) for i in ids))
        parties: dict = {}
        seen = []
        existing = await politician_index(db, House.camara)
        for det, hist in zip(details, historicos, strict=True):
            st = det.get("ultimoStatus", {})
            ext = str(det["id"])
            name = st.get("nomeEleitoral") or st.get("nome") or det.get("nomeCivil")
            uf = st.get("siglaUf") or ""
            values = {
                "civil_name": det.get("nomeCivil") or name,
                "parliamentary_name": name,
                "party_id": await party_id(db, st.get("siglaPartido"), parties),
                "uf": uf,
                "photo_url": st.get("urlFoto"),
                "email": (st.get("gabinete") or {}).get("email") or st.get("email"),
                "social_links": det.get("redeSocial") or [],
                "in_office": (st.get("situacao") or "Exercício") == "Exercício",
                "office_periods": parse_office_periods(hist),
                "legislature": st.get("idLegislatura") or s.legislature,
            }
            keys = {"house": House.camara, "external_id": ext}
            if ext not in existing:
                values["slug"] = await unique_slug(db, name, uf, ext)
            await upsert(db, Politician, keys, values)
            seen.append(ext)
            run.items += 1
        if not s.sync_limit:
            # Quem saiu da lista da legislatura deixa de estar em exercício.
            await db.execute(
                update(Politician)
                .where(Politician.house == House.camara, Politician.external_id.not_in(seen))
                .values(in_office=False)
            )
        await db.commit()


async def sync_senado(senado: SenadoSource) -> None:
    s = get_settings()
    async with tracked("sync_politicians", "senado") as run, SessionLocal() as db:
        items = await senado.senadores_em_exercicio()
        if s.sync_limit:
            items = items[: s.sync_limit]
        parties: dict = {}
        seen = []
        existing = await politician_index(db, House.senado)
        for raw in items:
            d = parse_senador(raw)
            ext = d["external_id"]
            values = {
                "civil_name": d["civil_name"],
                "parliamentary_name": d["parliamentary_name"],
                "party_id": await party_id(db, d["party"], parties),
                "uf": d["uf"],
                "photo_url": d["photo_url"],
                "email": d["email"],
                "social_links": d["social_links"],
                "in_office": True,
                "legislature": s.legislature,
            }
            keys = {"house": House.senado, "external_id": ext}
            if ext not in existing:
                values["slug"] = await unique_slug(db, d["parliamentary_name"], d["uf"], ext)
            await upsert(db, Politician, keys, values)
            seen.append(ext)
            run.items += 1
        if not s.sync_limit and seen:
            await db.execute(
                update(Politician)
                .where(Politician.house == House.senado, Politician.external_id.not_in(seen))
                .values(in_office=False)
            )
        await db.commit()


async def run(camara: CamaraSource, senado: SenadoSource) -> None:
    await sync_camara(camara)
    await sync_senado(senado)

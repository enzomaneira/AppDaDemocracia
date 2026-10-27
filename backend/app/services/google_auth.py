"""Validação do ID token do "Entrar com Google" (Google Identity Services).

O frontend recebe um ID token assinado pelo Google; aqui ele é conferido no endpoint
oficial `tokeninfo`, que verifica assinatura e validade. Além disso exigimos que o token
tenha sido emitido pelo Google para o nosso Client ID e que o e-mail esteja verificado.
Nenhuma senha passa pelo app.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}


class GoogleTokenError(Exception):
    """Token recusado (inválido, de outro app ou com e-mail não verificado)."""


class GoogleUnavailableError(Exception):
    """Não foi possível falar com o Google agora."""


@dataclass(frozen=True)
class GoogleIdentity:
    email: str
    name: str | None
    subject: str  # id estável da conta Google ("sub")


async def verify_id_token(id_token: str, client_id: str) -> GoogleIdentity:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(TOKENINFO_URL, params={"id_token": id_token})
    except httpx.HTTPError as e:
        raise GoogleUnavailableError from e
    if r.status_code >= 500:
        raise GoogleUnavailableError
    if r.status_code != 200:
        raise GoogleTokenError("token rejeitado pelo Google")
    info = r.json()
    if info.get("aud") != client_id:
        raise GoogleTokenError("token emitido para outro aplicativo")
    if info.get("iss") not in GOOGLE_ISSUERS:
        raise GoogleTokenError("emissor do token não é o Google")
    if info.get("email_verified") not in ("true", True) or not info.get("email"):
        raise GoogleTokenError("e-mail da conta Google não verificado")
    return GoogleIdentity(
        email=info["email"].lower(), name=info.get("name"), subject=str(info.get("sub", ""))
    )

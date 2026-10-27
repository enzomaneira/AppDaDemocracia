from datetime import UTC, datetime, timedelta

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from app.api.deps import DB
from app.core.config import get_settings
from app.core.ratelimit import limiter
from app.core.security import (
    create_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    verify_password,
)
from app.models import RefreshToken, User
from app.schemas import GoogleIn, LoginIn, RefreshIn, RegisterIn, TokenOut

router = APIRouter(prefix="/auth", tags=["auth"])
AUTH_LIMIT = get_settings().auth_rate_limit


async def _issue_tokens(db: DB, user: User) -> TokenOut:
    s = get_settings()
    token, token_hash = new_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(UTC) + timedelta(days=s.refresh_expires_days),
        )
    )
    await db.commit()
    return TokenOut(
        access_token=create_access_token(user.id, user.role),
        refresh_token=token,
        expires_in=s.jwt_expires_min * 60,
    )


async def _active_user_by_email(db: DB, email: str) -> User | None:
    q = select(User).where(User.email == email.lower(), User.deleted_at.is_(None))
    return (await db.execute(q)).scalar_one_or_none()


@router.post("/register", response_model=TokenOut, status_code=201)
@limiter.limit(AUTH_LIMIT)
async def register(request: Request, body: RegisterIn, db: DB) -> TokenOut:
    if not body.accept_terms:
        raise HTTPException(400, "É preciso aceitar os termos de uso e a política de privacidade")
    if await _active_user_by_email(db, body.email):
        raise HTTPException(409, "E-mail já cadastrado")
    user = User(
        email=body.email.lower(),
        name=body.name.strip(),
        password_hash=hash_password(body.password),
        auth_provider="email",
        uf=body.uf.upper() if body.uf else None,
    )
    db.add(user)
    await db.flush()
    return await _issue_tokens(db, user)


@router.post("/login", response_model=TokenOut)
@limiter.limit(AUTH_LIMIT)
async def login(request: Request, body: LoginIn, db: DB) -> TokenOut:
    user = await _active_user_by_email(db, body.email)
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-mail ou senha incorretos")
    return await _issue_tokens(db, user)


@router.post("/refresh", response_model=TokenOut)
@limiter.limit(AUTH_LIMIT)
async def refresh(request: Request, body: RefreshIn, db: DB) -> TokenOut:
    q = select(RefreshToken).where(
        RefreshToken.token_hash == hash_refresh_token(body.refresh_token)
    )
    rt = (await db.execute(q)).scalar_one_or_none()
    now = datetime.now(UTC)
    if not rt or rt.revoked_at or rt.expires_at < now:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sessão expirada, faça login novamente")
    user = await db.get(User, rt.user_id)
    if not user or user.deleted_at:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuário não encontrado")
    rt.revoked_at = now  # rotação: cada refresh token vale uma vez
    return await _issue_tokens(db, user)


@router.post("/logout", status_code=204)
async def logout(body: RefreshIn, db: DB) -> None:
    q = select(RefreshToken).where(
        RefreshToken.token_hash == hash_refresh_token(body.refresh_token)
    )
    rt = (await db.execute(q)).scalar_one_or_none()
    if rt and not rt.revoked_at:
        rt.revoked_at = datetime.now(UTC)
        await db.commit()


@router.post("/google", response_model=TokenOut)
@limiter.limit(AUTH_LIMIT)
async def google(request: Request, body: GoogleIn, db: DB) -> TokenOut:
    """Recebe o ID token do Google Identity Services e valida no endpoint oficial."""
    s = get_settings()
    if not s.google_client_id:
        raise HTTPException(501, "Login com Google não configurado")
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            "https://oauth2.googleapis.com/tokeninfo", params={"id_token": body.id_token}
        )
    info = r.json() if r.status_code == 200 else {}
    if info.get("aud") != s.google_client_id or info.get("email_verified") not in ("true", True):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token do Google inválido")

    user = await _active_user_by_email(db, info["email"])
    if not user:
        user = User(
            email=info["email"].lower(),
            name=info.get("name") or info["email"].split("@")[0],
            auth_provider="google",
        )
        db.add(user)
        await db.flush()
    return await _issue_tokens(db, user)

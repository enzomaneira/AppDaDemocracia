import uuid
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import User

DB = Annotated[AsyncSession, Depends(get_db)]
_bearer = HTTPBearer(auto_error=False)


async def get_optional_user(
    db: DB, creds: HTTPAuthorizationCredentials | None = Depends(_bearer)
) -> User | None:
    if not creds:
        return None
    try:
        payload = decode_access_token(creds.credentials)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido ou expirado") from None
    user = await db.get(User, uuid.UUID(payload["sub"]))
    if not user or user.deleted_at:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuário não encontrado")
    return user


async def get_current_user(user: User | None = Depends(get_optional_user)) -> User:
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Faça login para continuar")
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Acesso restrito a administradores")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]
AdminUser = Annotated[User, Depends(require_admin)]

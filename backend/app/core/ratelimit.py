import jwt
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from app.core.config import get_settings


def user_or_ip(request: Request) -> str:
    """Rate limit por usuário autenticado; sem login, por IP (RNF04)."""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        try:
            payload = jwt.decode(auth[7:], get_settings().jwt_secret, algorithms=["HS256"])
            return f"user:{payload['sub']}"
        except jwt.PyJWTError:
            pass
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(key_func=user_or_ip, default_limits=[get_settings().rate_limit])

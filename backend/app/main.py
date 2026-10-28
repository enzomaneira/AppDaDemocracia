from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1 import auth, bills, compare, me, misc, politicians, votes, waitlist
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.ratelimit import limiter

settings = get_settings()
setup_logging(settings.log_level)

app = FastAPI(
    title="App da Democracia API",
    version="0.1.0",
    description="Dados oficiais da Câmara e do Senado, com link para a fonte.",
    docs_url="/docs",
    openapi_url="/api/v1/openapi.json",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

v1 = APIRouter(prefix="/api/v1")
routers = (auth, me, politicians, bills, votes, compare, waitlist, misc)
for r in (m.router for m in routers):
    v1.include_router(r)
app.include_router(v1)

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    # Sem DATABASE_URL, usa SQLite em backend/dev.db (independe da pasta de onde se roda).
    database_url: str = f"sqlite+aiosqlite:///{BACKEND_DIR / 'dev.db'}"
    jwt_secret: str = "troque-este-segredo-em-producao-com-32+-caracteres"
    jwt_expires_min: int = 15
    refresh_expires_days: int = 30
    google_client_id: str = ""
    google_client_secret: str = ""
    cors_origins: list[str] = ["http://localhost:5173"]
    news_api_key: str = ""
    llm_api_key: str = ""
    log_level: str = "INFO"
    rate_limit: str = "120/minute"
    auth_rate_limit: str = "10/minute"

    # Ingestão
    camara_base_url: str = "https://dadosabertos.camara.leg.br/api/v2"
    senado_base_url: str = "https://legis.senado.leg.br/dadosabertos"
    legislature: int = 57
    # Limita quantos parlamentares por casa são sincronizados (0 = todos). Útil em dev.
    sync_limit: int = 0
    # Quantos dias para trás buscar votações, presença, proposições (1 = só ontem; maior = carga).
    sync_days_back: int = 1
    agenda_days_ahead: int = 14
    http_concurrency: int = 5
    news_feeds: list[str] = [
        "https://www.camara.leg.br/noticias/rss/ultimas-noticias",
        "https://www12.senado.leg.br/noticias/rss",
    ]

    @field_validator("database_url")
    @classmethod
    def _async_driver(cls, v: str) -> str:
        # O Railway entrega postgres:// ou postgresql://; o SQLAlchemy async precisa do asyncpg.
        if v.startswith("postgres://"):
            v = "postgresql://" + v.removeprefix("postgres://")
        if v.startswith("postgresql://"):
            v = "postgresql+asyncpg://" + v.removeprefix("postgresql://")
        return v

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")


@lru_cache
def get_settings() -> Settings:
    return Settings()

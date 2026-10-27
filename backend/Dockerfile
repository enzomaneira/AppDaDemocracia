FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
COPY ingestion ./ingestion
RUN pip install .

COPY alembic.ini ./
COPY alembic ./alembic

# Serviço "api". O serviço "sync-diario" usa a mesma imagem com:
#   python -m ingestion.run_daily
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]

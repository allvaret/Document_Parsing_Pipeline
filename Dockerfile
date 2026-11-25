# API somente leitura (FastAPI). O batch NÃO roda aqui: ele gera os dados fora do container.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/src

WORKDIR /app
COPY docker/requirements-api.txt docker/requirements-api.txt
RUN pip install --no-cache-dir -r docker/requirements-api.txt

# Só o código que a API e as migrações precisam.
COPY src/db src/db
COPY src/resumo src/resumo
COPY src/site_backend src/site_backend
COPY alembic.ini .
COPY migrations migrations

RUN useradd --system --uid 10001 app
USER app

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=10 \
  CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/health')" || exit 1

# Aplica as migrações e sobe a API. --proxy-headers: o IP real do cliente vem do proxy da hospedagem.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn site_backend.main:app --host 0.0.0.0 --port 8000 --proxy-headers"]

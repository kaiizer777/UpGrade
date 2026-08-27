# syntax=docker/dockerfile:1
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1

WORKDIR /app

# System deps for asyncpg/psycopg build + curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
  && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency manifests first for layer caching
COPY pyproject.toml uv.lock README.md ./

# Install deps (frozen, no dev) - creates .venv in /app if needed, but we use system python via UV_SYSTEM_PYTHON
RUN uv sync --frozen --no-dev --no-install-project

# Copy rest of project
COPY . .

# Sync project itself (installs backend package in env)
RUN uv sync --frozen --no-dev

EXPOSE 8000

# Healthcheck hits /health (fastapi)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/health || exit 1

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ---------------------------------------------------------------------------
# Worker note (arq):
# Run a second container from the same image with an overridden command:
#   uv run arq app.workers.feed.WorkerSettings
# Example docker-compose snippet:
#
#   services:
#     web:
#       build: ./backend
#       ports: ["8000:8000"]
#       env_file: .env
#       command: uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
#     worker:
#       build: ./backend
#       env_file: .env
#       command: uv run arq app.workers.feed.WorkerSettings
#       depends_on: [web]
# ---------------------------------------------------------------------------

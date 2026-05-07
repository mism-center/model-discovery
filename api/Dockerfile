# MISM Gateway API — production image (FastAPI + uvicorn)
FROM python:3.12-slim-bookworm

ARG PORT=8000

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    PORT=${PORT}

RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

RUN groupadd --system app && useradd --system --gid app --no-create-home app

COPY --chown=app:app pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY --chown=app:app src ./src
RUN uv sync --frozen --no-dev

USER app

ENV PATH="/app/.venv/bin:${PATH}"

EXPOSE ${PORT}

CMD ["sh", "-c", "exec uvicorn --app-dir src mismapi.main:app --host 0.0.0.0 --port ${PORT}"]

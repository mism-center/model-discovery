# MISM Gateway API — production image (FastAPI + uvicorn)
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY src ./src

RUN uv sync --frozen --no-dev \
    && groupadd --system app \
    && useradd --system --gid app --no-create-home app \
    && chown -R app:app /app

USER app

ENV PATH="/app/.venv/bin:${PATH}"

EXPOSE 8000

# Bind all interfaces; port is overridden in Kubernetes via container args or env if needed
CMD ["uvicorn", "--app-dir", "src", "mismapi.main:app", "--host", "0.0.0.0", "--port", "8000"]

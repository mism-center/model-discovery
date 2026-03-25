# MISM Gateway API — production image (FastAPI + uvicorn)
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy

RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY src ./src

# Allow git to clone private repos during build
ARG GIT_TOKEN=""
RUN if [ -n "$GIT_TOKEN" ]; then \
      git config --global url."https://x-access-token:${GIT_TOKEN}@github.com/".insteadOf "https://github.com/"; \
    fi \
    && uv sync --frozen --no-dev \
    && rm -f /root/.gitconfig \
    && groupadd --system app \
    && useradd --system --gid app --no-create-home app \
    && chown -R app:app /app

USER app

ENV PATH="/app/.venv/bin:${PATH}"

EXPOSE 8000

# Bind all interfaces; port is overridden in Kubernetes via container args or env if needed
CMD ["uvicorn", "--app-dir", "src", "mismapi.main:app", "--host", "0.0.0.0", "--port", "8000"]

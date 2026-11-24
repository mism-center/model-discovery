"""Shared fixtures for HTTP tests against a running API (e.g. Docker Compose).

Run after stack is up:
    docker compose -f ../docker-compose.test.yaml up -d --build --wait
    uv run pytest tests/integration/live -m integration -v
"""

from __future__ import annotations

import os
from collections.abc import Generator

import httpx
import pytest

BASE_URL = os.environ.get("INTEGRATION_TEST_BASE_URL", "http://localhost:8000")


@pytest.fixture()
def api() -> Generator[httpx.Client, None, None]:
    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        yield client

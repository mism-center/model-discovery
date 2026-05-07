"""Live checks against a running gateway (Docker)."""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.integration


def test_healthz(api: httpx.Client) -> None:
    r = api.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

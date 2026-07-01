"""
Shared test fixtures and helpers.

Tests inject a `Settings` instance into `create_app`. `make_settings` builds
one with `.env` loading disabled and a common set of test-safe defaults, so
individual tests only provide the values relevant to their assertions.

`mismapi.main` creates a module-level ASGI app at import time. Because some
production settings are intentionally required, this file also seeds matching
environment defaults before importing `create_app`; that keeps test collection
from depending on a developer's shell environment.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

TEST_SETTINGS_DEFAULTS: dict[str, Any] = {
    "DATABASE_URL": "postgresql+psycopg://postgres:postgres@localhost/mism_test",
    "REDIS_URL": "redis://localhost:6379/15",
    "TUSD_BASE_URL": "http://tusd.test",
    "AUTH_MODE": "oidc",
    "OIDC_ISSUER_URL": "https://issuer.example.com",
    "OIDC_AUDIENCE": "discovery-api",
    "OIDC_CLIENT_ID": "discovery-api",
    "OIDC_CLIENT_SECRET": "x",
    "OIDC_REDIRECT_URI": "https://gateway.example.com/api/auth/callback",
    "OIDC_COOKIE_SIGNING_SECRET": "test-cookie-signing-secret-please-change",
}

for _key, _value in TEST_SETTINGS_DEFAULTS.items():
    os.environ.setdefault(_key, str(_value))

from mismapi.auth.base import AuthenticatedPrincipal, require_principal  # noqa: E402
from mismapi.core.container import AppContainer  # noqa: E402
from mismapi.core.settings import Settings  # noqa: E402
from mismapi.main import create_app  # noqa: E402


class TestSettings(Settings):
    """Settings variant for tests that never read the project's `.env` file."""

    model_config = Settings.model_config | {"env_file": None}


def make_settings(**overrides: Any) -> Settings:
    """Construct test settings with sensible defaults and no `.env` loading."""
    values = dict(TEST_SETTINGS_DEFAULTS)
    values.update(overrides)
    return TestSettings(**values)


def minimal_oidc_settings(**overrides: Any) -> Settings:
    """Return a `Settings` that satisfies `ensure_startup_config` for OIDC mode."""
    base: dict[str, Any] = {}
    base.update(overrides)
    return make_settings(**base)


@contextmanager
def build_test_app(settings: Settings) -> Iterator[FastAPI]:
    """Yield a fresh FastAPI app wired with the provided `Settings`."""
    yield create_app(settings=settings)


@contextmanager
def build_test_client(
    settings: Settings,
    *,
    configure: Callable[[FastAPI], None] | None = None,
) -> Iterator[tuple[FastAPI, TestClient]]:
    """Yield `(app, client)` wired with settings and an optional configure hook."""
    with build_test_app(settings) as app:
        if configure is not None:
            configure(app)
        with TestClient(app) as client:
            yield app, client


def container_of(app: FastAPI) -> AppContainer:
    """Return the `AppContainer` wired into the given app (after `lifespan` has run)."""
    container: AppContainer = app.state.container
    return container


def default_principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        subject="user-1",
        issuer="https://issuer.example.com",
        audience="mism-api",
        scopes=set(),
    )


def override_principal(
    app: FastAPI,
    principal: AuthenticatedPrincipal | None = None,
) -> AuthenticatedPrincipal:
    """Register a `require_principal` override that returns a fixed principal."""
    effective = principal if principal is not None else default_principal()

    async def _override() -> AuthenticatedPrincipal:
        return effective

    app.dependency_overrides[require_principal] = _override
    return effective

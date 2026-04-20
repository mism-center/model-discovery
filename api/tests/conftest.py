"""
Shared test fixtures and helpers.

Tests inject a `Settings` instance into `create_app` instead of mutating
`os.environ`. `make_settings` builds a `Settings` with `.env` loading
disabled so results depend only on the explicit kwargs the test passes.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mismapi.auth.base import AuthenticatedPrincipal, require_principal
from mismapi.core.container import AppContainer
from mismapi.core.settings import Settings
from mismapi.main import create_app


def make_settings(**overrides: Any) -> Settings:
    """Construct a `Settings` for tests, skipping `.env` file loading."""
    return Settings(_env_file=None, **overrides)  # type: ignore[call-arg]


def minimal_oidc_settings(**overrides: Any) -> Settings:
    """Return a `Settings` that satisfies `ensure_startup_config` for OIDC mode."""
    base: dict[str, Any] = {
        "AUTH_MODE": "oidc",
        "OIDC_ISSUER_URL": "https://issuer.example.com",
        "OIDC_AUDIENCE": "discovery-api",
        "OIDC_CLIENT_ID": "discovery-api",
        "OIDC_CLIENT_SECRET": "x",
        "OIDC_REDIRECT_URI": "https://gateway.example.com/api/auth/callback",
    }
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

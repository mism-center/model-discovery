"""Shared test fixtures and helpers.

Centralizes the env-override + settings-cache-clear + app-build dance that was
previously duplicated across several test modules.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mismapi.auth.base import (
    AuthenticatedPrincipal,
    require_principal,
    subject_access_token_for_upstream_exchange,
)
from mismapi.core.container import AppContainer
from mismapi.core.settings import clear_settings_cache
from mismapi.main import create_app


@contextmanager
def temporary_env(overrides: dict[str, str]) -> Iterator[None]:
    """Temporarily set environment variables and ensure Settings is rebuilt."""
    previous: dict[str, str | None] = {key: os.environ.get(key) for key in overrides}
    try:
        for key, value in overrides.items():
            os.environ[key] = value
        clear_settings_cache()
        yield
    finally:
        for key in overrides:
            prior = previous[key]
            if prior is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = prior
        clear_settings_cache()


@contextmanager
def build_test_app(env_overrides: dict[str, str] | None = None) -> Iterator[FastAPI]:
    """Yield a fresh FastAPI app built with the given env overrides in effect."""
    env = env_overrides or {}
    with temporary_env(env):
        app = create_app()
        yield app


@contextmanager
def build_test_client(
    env_overrides: dict[str, str] | None = None,
    *,
    configure: Callable[[FastAPI], None] | None = None,
) -> Iterator[tuple[FastAPI, TestClient]]:
    """Yield `(app, client)` wired with env overrides and an optional configure hook."""
    with build_test_app(env_overrides) as app:
        if configure is not None:
            configure(app)
        with TestClient(app) as client:
            yield app, client


def container_of(app: FastAPI) -> AppContainer:
    """Return the AppContainer wired into the given app (after `lifespan` has run)."""
    container: AppContainer = app.state.container
    return container


def minimal_oidc_env(**overrides: str) -> dict[str, str]:
    """Return a dict that satisfies `ensure_startup_config` for OIDC mode.

    Individual tests spread this into their ``build_test_app`` env and then
    override or extend whatever they care about. Keeps tests focused on the
    behavior they're exercising instead of repeating the full set of OIDC
    envs required for the app to start.
    """
    base: dict[str, str] = {
        "AUTH_MODE": "oidc",
        "OIDC_ISSUER_URL": "https://issuer.example.com",
        "OIDC_AUDIENCE": "discovery-api",
        "OIDC_CLIENT_ID": "discovery-api",
        "OIDC_CLIENT_SECRET": "x",
        "OIDC_REDIRECT_URI": "https://gateway.example.com/api/auth/callback",
    }
    base.update(overrides)
    return base


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
    """Register `require_principal` override returning a fixed principal."""
    effective = principal if principal is not None else default_principal()

    async def _override() -> AuthenticatedPrincipal:
        return effective

    app.dependency_overrides[require_principal] = _override
    return effective


def override_subject_access_token(app: FastAPI, token: str = "test-subject-token") -> str:
    """Register `subject_access_token_for_upstream_exchange` override."""

    async def _override() -> str:
        return token

    app.dependency_overrides[subject_access_token_for_upstream_exchange] = _override
    return token

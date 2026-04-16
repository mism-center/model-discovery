import json
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jwt.algorithms import RSAAlgorithm

from mismapi.auth.base import (
    AuthenticatedPrincipal,
    require_principal,
    subject_access_token_for_upstream_exchange,
)
from mismapi.auth.oidc import (
    JWT_ACCESS_TOKEN_TYPE,
    ExchangedAccessTokenResult,
    OIDCDiscoveryDocument,
)
from mismapi.auth.oidc_auth_validator import OIDCAuthValidator
from mismapi.core.settings import Settings, clear_settings_cache
from mismapi.main import create_app


@contextmanager
def _temporary_env(overrides: dict[str, str]) -> Iterator[None]:
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


async def _principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        subject="user-1",
        issuer="https://issuer.example.com",
        audience="discovery-api",
        scopes={"openid"},
    )


async def _subject_token() -> str:
    return "ignored-when-exchange-is-mocked"


def test_execution_requires_oidc_mode() -> None:
    with _temporary_env({"AUTH_MODE": "jwt"}):
        app = create_app()
        app.dependency_overrides[require_principal] = _principal
        app.dependency_overrides[subject_access_token_for_upstream_exchange] = _subject_token
        with TestClient(app) as client:
            response = client.post("/api/v1/executions", json={})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "execution_oidc_only"


def test_execution_requires_token_exchange_audience() -> None:
    with _temporary_env(
        {
            "AUTH_MODE": "oidc",
            "OIDC_ISSUER_URL": "https://issuer.example.com",
            "OIDC_AUDIENCE": "discovery-api",
            "OIDC_REQUIRED_SCOPES": "openid",
            "OIDC_CLIENT_ID": "discovery-api",
            "OIDC_CLIENT_SECRET": "x",
            "OIDC_TOKEN_EXCHANGE_AUDIENCE": "",
            "STUB_UPSTREAM_SERVICES": "true",
        }
    ):
        app = create_app()
        app.dependency_overrides[require_principal] = _principal
        app.dependency_overrides[subject_access_token_for_upstream_exchange] = _subject_token
        with TestClient(app) as client:
            response = client.post("/api/v1/executions", json={})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "execution_token_exchange_unconfigured"


def test_execution_stub_happy_path() -> None:
    with _temporary_env(
        {
            "AUTH_MODE": "oidc",
            "OIDC_ISSUER_URL": "https://issuer.example.com",
            "OIDC_AUDIENCE": "discovery-api",
            "OIDC_REQUIRED_SCOPES": "openid",
            "OIDC_CLIENT_ID": "discovery-api",
            "OIDC_CLIENT_SECRET": "x",
            "OIDC_TOKEN_EXCHANGE_AUDIENCE": "helx",
            "STUB_UPSTREAM_SERVICES": "true",
        }
    ):
        app = create_app()
        with TestClient(app) as client:
            private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            public_key = private_key.public_key()
            jwk_payload = json.loads(RSAAlgorithm.to_jwk(key_obj=public_key))
            jwk_payload["kid"] = "key-1"

            settings: Settings = app.state.settings

            validator = OIDCAuthValidator(settings=settings)
            validator._issuer = "https://issuer.example.com"
            validator._jwks_uri = "https://issuer.example.com/jwks"
            validator._jwks_cache = {"key-1": jwk_payload}
            validator._jwks_cached_at = time.time()
            app.state.auth_validator = validator

            helx_access = jwt.encode(
                payload={
                    "iss": "https://issuer.example.com",
                    "aud": "helx",
                    "sub": "user-1",
                    "exp": int(time.time()) + 300,
                },
                key=private_key,
                algorithm="RS256",
                headers={"kid": "key-1"},
            )

            discovery = OIDCDiscoveryDocument(
                issuer="https://issuer.example.com",
                authorization_endpoint="https://issuer.example.com/auth",
                token_endpoint="https://issuer.example.com/token",
                jwks_uri="https://issuer.example.com/jwks",
                end_session_endpoint="",
            )
            loader = app.state.oidc_discovery_loader
            loader._cached = discovery

            app.dependency_overrides[require_principal] = _principal
            app.dependency_overrides[subject_access_token_for_upstream_exchange] = _subject_token

            fake_exchange = AsyncMock(
                return_value=ExchangedAccessTokenResult(
                    access_token=helx_access,
                    issued_token_type=JWT_ACCESS_TOKEN_TYPE,
                    expires_in=120,
                )
            )

            with patch(
                "mismapi.api.v1.execution.exchange_access_token_for_audience",
                fake_exchange,
            ):
                response = client.post(
                    "/api/v1/executions",
                    json={"model_id": "m-1", "parameters": {"k": "v"}},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["state"] == "accepted"
            assert data["upstream_http_status"] == 202
            assert data["execution_id"] is not None
            assert data["exchanged_access_token_ttl_seconds"] == 120
            assert data["poll_after_seconds"] == 5
            fake_exchange.assert_awaited_once()

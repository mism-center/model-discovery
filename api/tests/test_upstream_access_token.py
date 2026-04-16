import json
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jwt.algorithms import RSAAlgorithm

from mismapi.auth.base import (
    AuthenticatedPrincipal,
    require_principal,
    subject_access_token_for_upstream_exchange,
)
from mismapi.auth.oidc_auth_validator import OIDCAuthValidator
from mismapi.core.errors import APIError
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


@pytest.mark.asyncio
async def test_validate_upstream_access_token_success() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    jwk_payload = json.loads(RSAAlgorithm.to_jwk(key_obj=public_key))
    jwk_payload["kid"] = "key-1"

    settings = Settings(
        AUTH_MODE="oidc",
        OIDC_AUDIENCE="discovery-api",
        OIDC_REQUIRED_SCOPES="",
    )
    validator = OIDCAuthValidator(settings=settings)
    validator._issuer = "https://issuer.example.com"
    validator._jwks_uri = "https://issuer.example.com/jwks"
    validator._jwks_cache = {"key-1": jwk_payload}
    validator._jwks_cached_at = time.time()

    token = jwt.encode(
        payload={
            "iss": "https://issuer.example.com",
            "aud": "helx",
            "sub": "user-9",
            "exp": int(time.time()) + 120,
        },
        key=private_key,
        algorithm="RS256",
        headers={"kid": "key-1"},
    )

    await validator.validate_upstream_access_token(
        token,
        expected_audience="helx",
        expected_subject="user-9",
    )


@pytest.mark.asyncio
async def test_validate_upstream_access_token_rejects_subject_mismatch() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    jwk_payload = json.loads(RSAAlgorithm.to_jwk(key_obj=public_key))
    jwk_payload["kid"] = "key-1"

    settings = Settings(
        AUTH_MODE="oidc",
        OIDC_AUDIENCE="discovery-api",
        OIDC_REQUIRED_SCOPES="",
    )
    validator = OIDCAuthValidator(settings=settings)
    validator._issuer = "https://issuer.example.com"
    validator._jwks_uri = "https://issuer.example.com/jwks"
    validator._jwks_cache = {"key-1": jwk_payload}
    validator._jwks_cached_at = time.time()

    token = jwt.encode(
        payload={
            "iss": "https://issuer.example.com",
            "aud": "helx",
            "sub": "user-9",
            "exp": int(time.time()) + 120,
        },
        key=private_key,
        algorithm="RS256",
        headers={"kid": "key-1"},
    )

    with pytest.raises(APIError) as excinfo:
        await validator.validate_upstream_access_token(
            token,
            expected_audience="helx",
            expected_subject="other-user",
        )
    assert excinfo.value.code == "auth_upstream_subject_mismatch"


def test_execution_requires_helx_url_when_not_stub() -> None:
    with _temporary_env(
        {
            "AUTH_MODE": "oidc",
            "OIDC_ISSUER_URL": "https://issuer.example.com",
            "OIDC_AUDIENCE": "discovery-api",
            "OIDC_REQUIRED_SCOPES": "openid",
            "OIDC_CLIENT_ID": "discovery-api",
            "OIDC_CLIENT_SECRET": "x",
            "OIDC_TOKEN_EXCHANGE_AUDIENCE": "helx",
            "STUB_UPSTREAM_SERVICES": "false",
            "HELX_EXEC_PLATFORM_BASE_URL": "",
        }
    ):
        app = create_app()

        async def principal_override() -> AuthenticatedPrincipal:
            return AuthenticatedPrincipal(
                subject="u",
                issuer="https://issuer.example.com",
                audience="discovery-api",
                scopes=set(),
            )

        async def subject_token_override() -> str:
            return "t"

        app.dependency_overrides[require_principal] = principal_override
        app.dependency_overrides[subject_access_token_for_upstream_exchange] = (
            subject_token_override
        )

        with TestClient(app) as client:
            response = client.post("/api/v1/executions", json={})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "execution_exec_platform_unconfigured"

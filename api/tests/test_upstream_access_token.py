import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jwt.algorithms import RSAAlgorithm

from mismapi.auth.jwks_cache import JWKSCache
from mismapi.auth.oidc_discovery import OIDCDiscoveryCache
from mismapi.auth.oidc_types import OIDCDiscoveryDocument
from mismapi.auth.validator import OIDCAuthValidator
from mismapi.core.errors import APIError
from mismapi.core.settings import Settings
from tests.conftest import (
    build_test_app,
    minimal_oidc_env,
    override_principal,
    override_subject_access_token,
)


def _validator_with_seeded_caches(
    settings: Settings,
    *,
    issuer: str,
    jwks_uri: str,
    keys: dict[str, dict[str, object]],
) -> OIDCAuthValidator:
    discovery_cache = OIDCDiscoveryCache(settings=settings)
    discovery_cache.seed(
        OIDCDiscoveryDocument(
            issuer=issuer,
            authorization_endpoint="",
            token_endpoint="",
            jwks_uri=jwks_uri,
            end_session_endpoint="",
        )
    )
    validator = OIDCAuthValidator(settings=settings, discovery_cache=discovery_cache)
    validator.jwks_cache = JWKSCache.from_keys(keys, uri=jwks_uri)
    return validator


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
    validator = _validator_with_seeded_caches(
        settings,
        issuer="https://issuer.example.com",
        jwks_uri="https://issuer.example.com/jwks",
        keys={"key-1": jwk_payload},
    )

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
    validator = _validator_with_seeded_caches(
        settings,
        issuer="https://issuer.example.com",
        jwks_uri="https://issuer.example.com/jwks",
        keys={"key-1": jwk_payload},
    )

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
    with build_test_app(
        minimal_oidc_env(
            OIDC_REQUIRED_SCOPES="openid",
            OIDC_TOKEN_EXCHANGE_AUDIENCE="helx",
            STUB_UPSTREAM_SERVICES="false",
            HELX_EXEC_PLATFORM_BASE_URL="",
        )
    ) as app:
        override_principal(app)
        override_subject_access_token(app, "t")

        with TestClient(app) as client:
            response = client.post("/api/v1/executions", json={})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "execution_exec_platform_unconfigured"

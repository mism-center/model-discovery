import json
import time
from unittest.mock import AsyncMock

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jwt.algorithms import RSAAlgorithm

from mismapi.auth.jwks_cache import JWKSCache
from mismapi.auth.oidc_discovery import OIDCDiscoveryCache
from mismapi.auth.oidc_types import (
    JWT_ACCESS_TOKEN_TYPE,
    ExchangedAccessTokenResult,
    OIDCDiscoveryDocument,
)
from mismapi.auth.validator import OIDCAuthValidator
from mismapi.core.settings import Settings
from tests.conftest import (
    build_test_app,
    container_of,
    default_principal,
    minimal_oidc_env,
    override_principal,
    override_subject_access_token,
)


def test_execution_requires_oidc_mode() -> None:
    with build_test_app({"AUTH_MODE": "jwt"}) as app:
        override_principal(app)
        override_subject_access_token(app)
        with TestClient(app) as client:
            response = client.post("/api/v1/executions", json={})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "oidc_validator_required"


def test_execution_requires_token_exchange_audience() -> None:
    with build_test_app(
        minimal_oidc_env(
            OIDC_REQUIRED_SCOPES="openid",
            OIDC_TOKEN_EXCHANGE_AUDIENCE="",
            STUB_UPSTREAM_SERVICES="true",
        )
    ) as app:
        override_principal(app)
        override_subject_access_token(app)
        with TestClient(app) as client:
            response = client.post("/api/v1/executions", json={})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "execution_token_exchange_unconfigured"


def test_execution_stub_happy_path() -> None:
    with build_test_app(
        minimal_oidc_env(
            OIDC_REQUIRED_SCOPES="openid",
            OIDC_TOKEN_EXCHANGE_AUDIENCE="helx",
            STUB_UPSTREAM_SERVICES="true",
        )
    ) as app:
        with TestClient(app) as client:
            private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            public_key = private_key.public_key()
            jwk_payload = json.loads(RSAAlgorithm.to_jwk(key_obj=public_key))
            jwk_payload["kid"] = "key-1"

            container = container_of(app)
            settings: Settings = container.settings

            discovery = OIDCDiscoveryDocument(
                issuer="https://issuer.example.com",
                authorization_endpoint="https://issuer.example.com/auth",
                token_endpoint="https://issuer.example.com/token",
                jwks_uri="https://issuer.example.com/jwks",
                end_session_endpoint="",
            )
            container.oidc_discovery_cache.seed(discovery)

            discovery_cache = OIDCDiscoveryCache(settings=settings)
            discovery_cache.seed(discovery)
            validator = OIDCAuthValidator(
                settings=settings,
                discovery_cache=discovery_cache,
            )
            validator.jwks_cache = JWKSCache.from_keys({"key-1": jwk_payload})
            container.auth_validator = validator

            helx_access = jwt.encode(
                payload={
                    "iss": "https://issuer.example.com",
                    "aud": "helx",
                    "sub": default_principal().subject,
                    "exp": int(time.time()) + 300,
                },
                key=private_key,
                algorithm="RS256",
                headers={"kid": "key-1"},
            )

            override_principal(app)
            override_subject_access_token(app)

            fake_exchange = AsyncMock(
                return_value=ExchangedAccessTokenResult(
                    access_token=helx_access,
                    issued_token_type=JWT_ACCESS_TOKEN_TYPE,
                    expires_in=120,
                )
            )
            container.oidc_service.exchange_for_audience = fake_exchange  # type: ignore[method-assign]

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

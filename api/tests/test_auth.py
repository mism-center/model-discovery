import json

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jwt.algorithms import RSAAlgorithm

from mismapi.auth.base import build_auth_validator
from mismapi.auth.jwks_cache import JWKSCache
from mismapi.auth.oidc_discovery import OIDCDiscoveryCache
from mismapi.auth.oidc_types import OIDCDiscoveryDocument
from mismapi.auth.validator import JWTAuthValidator, OIDCAuthValidator
from mismapi.core.container import AppContainer
from mismapi.core.settings import Settings
from tests.conftest import build_test_app, temporary_env


def _settings_with_env(env_overrides: dict[str, str]) -> Settings:
    with temporary_env(env_overrides):
        return Settings()


def test_route_requires_bearer_token() -> None:
    with build_test_app({"AUTH_MODE": "jwt"}) as app:
        with TestClient(app) as client:
            response = client.get("/api/v1/models?q=test")
            assert response.status_code == 401
            payload = response.json()
            assert payload["error"]["code"] == "auth_missing"


def test_build_auth_validator_selects_jwt() -> None:
    settings = _settings_with_env({"AUTH_MODE": "jwt"})
    validator = build_auth_validator(settings=settings)
    assert isinstance(validator, JWTAuthValidator)


def test_build_auth_validator_selects_oidc() -> None:
    settings = _settings_with_env({"AUTH_MODE": "oidc"})
    validator = build_auth_validator(settings=settings)
    assert isinstance(validator, OIDCAuthValidator)


async def test_jwt_auth_validator_validates_token() -> None:
    settings = _settings_with_env(
        {
            "AUTH_MODE": "jwt",
            "JWT_ISSUER": "https://issuer.example.com",
            "JWT_AUDIENCE": "mism-api",
            "JWT_ALGORITHMS": "HS256",
            "JWT_PUBLIC_KEY": "0123456789abcdef0123456789abcdef",
        }
    )
    validator = JWTAuthValidator(settings=settings)
    token = jwt.encode(
        payload={
            "iss": "https://issuer.example.com",
            "aud": "mism-api",
            "sub": "user-1",
            "scope": "read write",
        },
        key="0123456789abcdef0123456789abcdef",
        algorithm="HS256",
    )

    principal = await validator.validate_token(token=token)
    assert principal.subject == "user-1"
    assert "read" in principal.scopes


async def test_oidc_auth_validator_validates_token_with_cached_jwks() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    jwk_payload = json.loads(RSAAlgorithm.to_jwk(key_obj=public_key))
    jwk_payload["kid"] = "key-1"

    settings = _settings_with_env(
        {
            "AUTH_MODE": "oidc",
            "OIDC_AUDIENCE": "mism-api",
            "OIDC_REQUIRED_SCOPES": "read",
        }
    )
    discovery_cache = OIDCDiscoveryCache(settings=settings)
    discovery_cache.seed(
        OIDCDiscoveryDocument(
            issuer="https://issuer.example.com",
            authorization_endpoint="",
            token_endpoint="",
            jwks_uri="https://issuer.example.com/jwks",
            end_session_endpoint="",
        )
    )
    validator = OIDCAuthValidator(settings=settings, discovery_cache=discovery_cache)
    validator.jwks_cache = JWKSCache.from_keys({"key-1": jwk_payload})

    token = jwt.encode(
        payload={
            "iss": "https://issuer.example.com",
            "aud": "mism-api",
            "sub": "user-2",
            "scope": "read write",
        },
        key=private_key,
        algorithm="RS256",
        headers={"kid": "key-1"},
    )

    principal = await validator.validate_token(token=token)
    assert principal.subject == "user-2"
    assert "read" in principal.scopes


def test_route_unexpected_auth_error_returns_internal_server_error() -> None:
    class BrokenAuthValidator:
        async def validate_token(self, token: str) -> object:
            raise RuntimeError("unexpected validator failure")

    with build_test_app({"AUTH_MODE": "jwt"}) as app:
        with TestClient(app, raise_server_exceptions=False) as client:
            container: AppContainer = app.state.container
            container.auth_validator = BrokenAuthValidator()  # type: ignore[assignment]
            response = client.get(
                "/api/v1/models?q=test",
                headers={"Authorization": "Bearer token-value"},
            )
            assert response.status_code == 500

import json
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from mismapi.auth.jwks_cache import JWKSCache
from mismapi.auth.validator import OIDCAuthValidator
from mismapi.core.settings import Settings


def _settings(**overrides: Any) -> Settings:
    return Settings(_env_file=None, **overrides)  # type: ignore[call-arg]


async def test_oidc_auth_validator_validates_token_with_cached_jwks() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    jwk_payload = json.loads(RSAAlgorithm.to_jwk(key_obj=public_key))
    jwk_payload["kid"] = "key-1"

    settings = _settings(
        AUTH_MODE="oidc",
        OIDC_AUDIENCE="mism-api",
        OIDC_REQUIRED_SCOPES="read",
    )

    async def issuer_loader() -> str:
        return "https://issuer.example.com"

    async def jwks_uri_loader() -> str:
        return "https://issuer.example.com/jwks"

    validator = OIDCAuthValidator(
        settings=settings,
        issuer_loader=issuer_loader,
        jwks_uri_loader=jwks_uri_loader,
    )
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

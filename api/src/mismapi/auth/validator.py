"""Auth validator protocol and concrete implementation.

* `AuthValidator` — Protocol the request path depends on.
* `OIDCAuthValidator` — Validates inbound OIDC-issued JWT access tokens
  against the IdP's signing keys and our configured audience/scopes.

The validator no longer owns OIDC discovery: it pulls `issuer` and
`jwks_uri` from a metadata loader callback supplied at construction time
(in practice, `OIDCService.load_issuer` / `load_jwks_uri`, which delegate
to Authlib's cached `load_server_metadata`). This keeps a single discovery
cache for the whole app instead of running the inbound validator and the
outbound OAuth client on parallel ones.

`AuthenticatedPrincipal` stays in `mismapi.auth.principal` as a pure,
dependency-free value type.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

import jwt
from jwt.algorithms import RSAAlgorithm

from mismapi.auth.jwks_cache import JWKSCache
from mismapi.auth.principal import AuthenticatedPrincipal
from mismapi.core.errors import APIError
from mismapi.core.settings import Settings

logger = logging.getLogger(__name__)


class AuthValidator(Protocol):
    """Validates a token and returns an `AuthenticatedPrincipal`."""

    async def validate_token(self, token: str) -> AuthenticatedPrincipal:
        raise NotImplementedError


IssuerLoader = Callable[[], Awaitable[str]]
JwksUriLoader = Callable[[], Awaitable[str]]


@dataclass(slots=True)
class OIDCAuthValidator:
    """Validates OIDC-issued JWT access tokens against cached JWKS."""

    settings: Settings
    issuer_loader: IssuerLoader
    jwks_uri_loader: JwksUriLoader
    jwks_cache: JWKSCache = field(init=False)

    def __post_init__(self) -> None:
        self.jwks_cache = JWKSCache(
            uri_supplier=self.jwks_uri_loader,
            ttl_seconds=self.settings.oidc_jwks_ttl_seconds,
        )

    async def validate_token(self, token: str) -> AuthenticatedPrincipal:
        """Validate an access_token: signature, issuer, audience, scopes."""
        issuer = await self.issuer_loader()
        unverified_header = jwt.get_unverified_header(token)
        key: Any = await self._resolve_key(unverified_header=unverified_header)
        payload = jwt.decode(
            token,
            key=key,
            algorithms=["RS256"],
            audience=self.settings.oidc_audience,
            issuer=issuer,
            leeway=self.settings.oidc_jwt_leeway_seconds,
        )

        scopes = _parse_scope_claim(payload=payload)
        required_scopes = set(self.settings.oidc_required_scope_list)
        if required_scopes and not required_scopes.issubset(scopes):
            raise APIError(
                status_code=403,
                code="auth_scope_missing",
                detail="Required scope is missing.",
            )

        subject = str(payload.get("sub", ""))
        if not subject:
            raise APIError(
                status_code=401,
                code="auth_invalid_sub",
                detail="Token subject is missing.",
            )

        return AuthenticatedPrincipal(
            subject=subject,
            issuer=issuer,
            audience=self.settings.oidc_audience,
            scopes=scopes,
        )

    async def _resolve_key(self, unverified_header: dict[str, str]) -> Any:
        """Resolve the JWK for a given token's `kid` header."""
        keys = await self.jwks_cache.get()
        kid = unverified_header.get("kid", "")
        if not kid:
            raise APIError(
                status_code=401,
                code="auth_missing_kid",
                detail="Token kid header missing.",
            )

        jwk_payload = keys.get(kid)
        if jwk_payload is None:
            raise APIError(
                status_code=401,
                code="auth_unknown_kid",
                detail="Unrecognized token key id.",
            )

        return RSAAlgorithm.from_jwk(json.dumps(jwk_payload))


def _parse_scope_claim(payload: dict[str, object]) -> set[str]:
    scope_value = payload.get("scope")
    if isinstance(scope_value, str):
        return {value for value in scope_value.split(" ") if value}

    scope_list = payload.get("scp")
    if isinstance(scope_list, list):
        return {str(value) for value in scope_list}

    return set()

"""Auth validator protocol and concrete implementation.

* `AuthValidator` — Protocol the request path depends on.
* `OIDCAuthValidator` — Validates inbound OIDC-issued JWT access tokens
  against the IdP's signing keys and our configured audience/scopes.

JWKS fetching and caching are delegated to PyJWT's `PyJWKClient`, which
provides TTL caching, single-flight kid lookup with auto-refresh on miss,
and key parsing in one component. The validator builds the client lazily
on first use because the JWKS URI is resolved through an async loader
(in practice `OIDCService.load_jwks_uri`, backed by Authlib's cached
`load_server_metadata`). `PyJWKClient.get_signing_key` is synchronous
(`urllib`-based), so calls are dispatched via `asyncio.to_thread`.

`AuthenticatedPrincipal` stays in `mismapi.auth.principal` as a pure,
dependency-free value type.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError, PyJWKClientError

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
    jwk_client: PyJWKClient | None = None
    _client_lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

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
        kid = unverified_header.get("kid", "")
        if not kid:
            raise APIError(
                status_code=401,
                code="auth_missing_kid",
                detail="Token kid header missing.",
            )

        client = await self._get_client()
        try:
            signing_key = await asyncio.to_thread(client.get_signing_key, kid)
        except PyJWKClientConnectionError as exc:
            raise APIError(
                status_code=503,
                code="auth_jwks_unavailable",
                detail="JWKS fetch failed.",
            ) from exc
        except PyJWKClientError as exc:
            # Covers unknown-kid (after refresh) and malformed JWKS responses.
            raise APIError(
                status_code=401,
                code="auth_unknown_kid",
                detail="Unrecognized token key id.",
            ) from exc

        return signing_key.key

    async def _get_client(self) -> PyJWKClient:
        if self.jwk_client is not None:
            return self.jwk_client
        async with self._client_lock:
            if self.jwk_client is not None:
                return self.jwk_client
            jwks_uri = await self.jwks_uri_loader()
            if not jwks_uri:
                raise APIError(
                    status_code=500,
                    code="auth_oidc_uninitialized",
                    detail="JWKS URI is not configured.",
                )
            logger.info("building_jwk_client url=%s", jwks_uri)
            self.jwk_client = PyJWKClient(
                jwks_uri,
                cache_jwk_set=True,
                lifespan=self.settings.oidc_jwks_ttl_seconds,
            )
            return self.jwk_client


def _parse_scope_claim(payload: dict[str, object]) -> set[str]:
    scope_value = payload.get("scope")
    if isinstance(scope_value, str):
        return {value for value in scope_value.split(" ") if value}

    scope_list = payload.get("scp")
    if isinstance(scope_list, list):
        return {str(value) for value in scope_list}

    return set()

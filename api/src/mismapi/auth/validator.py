"""Auth validator protocols and concrete implementations.

Consolidates the validator side of the auth module:

* `AuthValidator` / `OIDCValidator` — Protocols that describe what the
  request path depends on.
* `JWTAuthValidator` — stand-alone JWT bearer validation (`AUTH_MODE=jwt`).
* `OIDCAuthValidator` — OIDC access/id token validation backed by shared
  discovery + JWKS caches (`AUTH_MODE=oidc`).

`AuthenticatedPrincipal` stays in `mismapi.auth.principal` as a pure,
dependency-free value type so it can be imported without pulling anything
below in.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

import jwt
from jwt.algorithms import RSAAlgorithm

from mismapi.auth.jwks_cache import JWKSCache
from mismapi.auth.oidc_discovery import OIDCDiscoveryCache
from mismapi.auth.principal import AuthenticatedPrincipal
from mismapi.core.errors import APIError
from mismapi.core.settings import Settings

logger = logging.getLogger(__name__)


class AuthValidator(Protocol):
    """Validates a token and returns an `AuthenticatedPrincipal`."""

    async def validate_token(self, token: str) -> AuthenticatedPrincipal:
        raise NotImplementedError


class OIDCValidator(AuthValidator, Protocol):
    """
    An `AuthValidator` that also performs OIDC-specific validation.

    Handlers that need `verify_identity` (callback) or
    `validate_upstream_access_token` (exchanges) should `Depends` on this
    protocol rather than `isinstance`-checking `OIDCAuthValidator`.
    """

    async def verify_identity(self, id_token: str) -> str:
        raise NotImplementedError

    async def validate_upstream_access_token(
        self,
        token: str,
        *,
        expected_audience: str,
        expected_subject: str,
    ) -> None:
        raise NotImplementedError


@dataclass(slots=True)
class JWTAuthValidator:
    """Validates stand-alone JWTs against either a static public key or a shared JWKS cache."""

    settings: Settings
    jwks_cache: JWKSCache | None = None

    def __post_init__(self) -> None:
        if self.jwks_cache is None and self.settings.jwt_jwks_url:

            async def _uri() -> str:
                return self.settings.jwt_jwks_url

            self.jwks_cache = JWKSCache(
                uri_supplier=_uri,
                ttl_seconds=300,
            )

    async def validate_token(self, token: str) -> AuthenticatedPrincipal:
        unverified_header = jwt.get_unverified_header(token)
        key: Any = await self._resolve_verification_key(unverified_header=unverified_header)
        payload = jwt.decode(
            token,
            key=key,
            algorithms=self.settings.jwt_algorithm_list,
            audience=self.settings.jwt_audience,
            issuer=self.settings.jwt_issuer,
            leeway=self.settings.jwt_leeway_seconds,
        )
        scopes = _parse_scope_claim(payload)
        subject = str(payload.get("sub", ""))
        if not subject:
            raise APIError(
                status_code=401,
                code="auth_invalid_sub",
                detail="Token subject is missing.",
            )

        return AuthenticatedPrincipal(
            subject=subject,
            issuer=str(payload.get("iss", "")),
            audience=self.settings.jwt_audience,
            scopes=scopes,
        )

    async def _resolve_verification_key(self, unverified_header: dict[str, str]) -> Any:
        if self.jwks_cache is not None:
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

        if self.settings.jwt_public_key:
            return self.settings.jwt_public_key

        raise APIError(
            status_code=500,
            code="auth_misconfigured",
            detail="JWT validation is not configured with jwks_url or public key.",
        )


@dataclass(slots=True)
class OIDCAuthValidator:
    """Validates OIDC-issued JWTs using shared discovery + JWKS caches."""

    settings: Settings
    discovery_cache: OIDCDiscoveryCache
    jwks_cache: JWKSCache = field(init=False)

    def __post_init__(self) -> None:
        async def _jwks_uri() -> str:
            discovery = await self.discovery_cache.get()
            return discovery.jwks_uri

        self.jwks_cache = JWKSCache(
            uri_supplier=_jwks_uri,
            ttl_seconds=self.settings.oidc_jwks_ttl_seconds,
        )

    async def validate_token(self, token: str) -> AuthenticatedPrincipal:
        """Validate an access_token: signature, issuer, audience, scopes."""
        discovery = await self.discovery_cache.get()
        unverified_header = jwt.get_unverified_header(token)
        key: Any = await self._resolve_key(unverified_header=unverified_header)
        payload = jwt.decode(
            token,
            key=key,
            algorithms=["RS256"],
            audience=self.settings.oidc_audience,
            issuer=discovery.issuer,
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
            issuer=discovery.issuer,
            audience=self.settings.oidc_audience,
            scopes=scopes,
        )

    async def validate_upstream_access_token(
        self,
        token: str,
        *,
        expected_audience: str,
        expected_subject: str,
    ) -> None:
        """
        Validate an exchanged access token before forwarding it (signature, iss, aud, exp,
        sub binding to the gateway-authenticated user).
        """
        if not expected_audience.strip():
            raise APIError(
                status_code=500,
                code="auth_upstream_audience_missing",
                detail="Upstream JWT audience is not configured.",
            )

        discovery = await self.discovery_cache.get()
        unverified_header = jwt.get_unverified_header(token)
        key: Any = await self._resolve_key(unverified_header=unverified_header)
        try:
            payload = jwt.decode(
                token,
                key=key,
                algorithms=["RS256"],
                audience=expected_audience.strip(),
                issuer=discovery.issuer,
                leeway=self.settings.oidc_jwt_leeway_seconds,
            )
        except jwt.PyJWTError as exc:
            logger.warning("upstream_access_token_jwt_invalid error=%s", type(exc).__name__)
            raise APIError(
                status_code=502,
                code="auth_upstream_token_invalid",
                detail="Exchanged access token failed validation.",
            ) from exc

        subject = str(payload.get("sub", ""))
        if not subject or subject != expected_subject:
            raise APIError(
                status_code=502,
                code="auth_upstream_subject_mismatch",
                detail="Exchanged token subject does not match the current user.",
            )

    async def verify_identity(self, id_token: str) -> str:
        """
        Validate an id_token for identity only (signature, issuer, audience)
        and return the subject claim.
        """
        discovery = await self.discovery_cache.get()
        unverified_header = jwt.get_unverified_header(id_token)
        key: Any = await self._resolve_key(unverified_header=unverified_header)
        payload = jwt.decode(
            id_token,
            key=key,
            algorithms=["RS256"],
            audience=self.settings.oidc_client_id,
            issuer=discovery.issuer,
            leeway=self.settings.oidc_jwt_leeway_seconds,
        )

        subject = str(payload.get("sub", ""))
        if not subject:
            raise APIError(
                status_code=401,
                code="auth_invalid_sub",
                detail="Token subject is missing.",
            )

        return subject

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

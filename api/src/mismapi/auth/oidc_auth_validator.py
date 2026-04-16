import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
import jwt
from jwt.algorithms import RSAAlgorithm

from mismapi.auth.base import AuthenticatedPrincipal
from mismapi.core.errors import APIError
from mismapi.core.settings import Settings

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class OIDCAuthValidator:
    settings: Settings
    _jwks_uri: str = field(default="")
    _issuer: str = field(default="")
    _jwks_cache: dict[str, dict[str, object]] = field(default_factory=dict)
    _jwks_cached_at: float = field(default=0.0)

    async def validate_token(self, token: str) -> AuthenticatedPrincipal:
        """Validate an access_token: signature, issuer, audience, scopes."""
        if not self._jwks_uri:
            await self._load_discovery()

        unverified_header = jwt.get_unverified_header(token)
        key: Any = await self._resolve_key(unverified_header=unverified_header)
        payload = jwt.decode(
            token,
            key=key,
            algorithms=["RS256"],
            audience=self.settings.oidc_audience,
            issuer=self._issuer,
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
            issuer=self._issuer,
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
        Validate an exchanged access token before forwarding it to HeLx (signature, iss, aud, exp,
        sub binding to the gateway-authenticated user).
        """
        if not expected_audience.strip():
            raise APIError(
                status_code=500,
                code="auth_upstream_audience_missing",
                detail="Upstream JWT audience is not configured.",
            )
        if not self._jwks_uri:
            await self._load_discovery()

        unverified_header = jwt.get_unverified_header(token)
        key: Any = await self._resolve_key(unverified_header=unverified_header)
        try:
            payload = jwt.decode(
                token,
                key=key,
                algorithms=["RS256"],
                audience=expected_audience.strip(),
                issuer=self._issuer,
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
        if not self._jwks_uri:
            await self._load_discovery()

        unverified_header = jwt.get_unverified_header(id_token)
        key: Any = await self._resolve_key(unverified_header=unverified_header)
        payload = jwt.decode(
            id_token,
            key=key,
            algorithms=["RS256"],
            audience=self.settings.oidc_client_id,
            issuer=self._issuer,
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

    async def _load_discovery(self) -> None:
        discovery_url = self.settings.oidc_discovery_url
        if not discovery_url:
            issuer = self.settings.oidc_issuer_url.rstrip("/")
            discovery_url = f"{issuer}/.well-known/openid-configuration"

        logger.info("loading_oidc_discovery url=%s", discovery_url)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(discovery_url)
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError as exc:
            raise APIError(
                status_code=503,
                code="auth_oidc_discovery_unavailable",
                detail="OIDC discovery fetch failed.",
            ) from exc

        issuer = payload.get("issuer")
        jwks_uri = payload.get("jwks_uri")
        if not isinstance(issuer, str) or not isinstance(jwks_uri, str):
            raise APIError(
                status_code=503,
                code="auth_oidc_discovery_invalid",
                detail="OIDC discovery payload is invalid.",
            )

        self._issuer = issuer
        self._jwks_uri = jwks_uri

    async def _resolve_key(self, unverified_header: dict[str, str]) -> Any:
        keys = await self._load_jwks_keys()
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

    async def _load_jwks_keys(self) -> dict[str, dict[str, object]]:
        now = time.time()
        if self._jwks_cache and (now - self._jwks_cached_at) < self.settings.oidc_jwks_ttl_seconds:
            return self._jwks_cache

        if not self._jwks_uri:
            raise APIError(
                status_code=500,
                code="auth_oidc_uninitialized",
                detail="OIDC discovery has not been loaded.",
            )

        logger.info("refreshing_oidc_jwks url=%s", self._jwks_uri)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self._jwks_uri)
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError as exc:
            raise APIError(
                status_code=503,
                code="auth_jwks_unavailable",
                detail="OIDC JWKS fetch failed.",
            ) from exc

        keys_raw = payload.get("keys")
        if not isinstance(keys_raw, list):
            raise APIError(
                status_code=503,
                code="auth_jwks_invalid",
                detail="JWKS response is invalid.",
            )

        parsed: dict[str, dict[str, object]] = {}
        for key_item in keys_raw:
            if not isinstance(key_item, dict):
                continue
            kid = key_item.get("kid")
            if isinstance(kid, str) and kid:
                parsed[kid] = key_item

        self._jwks_cache = parsed
        self._jwks_cached_at = now
        return parsed


def _parse_scope_claim(payload: dict[str, object]) -> set[str]:
    scope_value = payload.get("scope")
    if isinstance(scope_value, str):
        return {value for value in scope_value.split(" ") if value}

    scope_list = payload.get("scp")
    if isinstance(scope_list, list):
        return {str(value) for value in scope_list}

    return set()

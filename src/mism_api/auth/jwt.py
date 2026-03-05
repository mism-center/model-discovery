import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
import jwt

from mism_api.auth.base import AuthenticatedPrincipal
from mism_api.core.errors import APIError
from mism_api.core.settings import Settings

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class JWTAuthValidator:
    settings: Settings
    _jwks_cache: dict[str, dict[str, object]] = field(default_factory=dict)
    _jwks_cached_at: float = field(default=0.0)
    _jwks_ttl_seconds: int = field(default=300)

    async def validate_token(self, token: str) -> AuthenticatedPrincipal:
        unverified_header = jwt.get_unverified_header(token)
        key: Any = await self._resolve_verification_key(unverified_header=unverified_header)
        payload = jwt.decode(
            token,
            key=key,
            algorithms=self.settings.jwt_algorithm_list,
            audience=self.settings.jwt_audience,
            issuer=self.settings.jwt_issuer,
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
        if self.settings.jwt_jwks_url:
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
            return jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk_payload))

        if self.settings.jwt_public_key:
            return self.settings.jwt_public_key

        raise APIError(
            status_code=500,
            code="auth_misconfigured",
            detail="JWT validation is not configured with jwks_url or public key.",
        )

    async def _load_jwks_keys(self) -> dict[str, dict[str, object]]:
        now = time.time()
        if self._jwks_cache and (now - self._jwks_cached_at) < self._jwks_ttl_seconds:
            return self._jwks_cache

        logger.info("refreshing_jwks_from_url url=%s", self.settings.jwt_jwks_url)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.settings.jwt_jwks_url)
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError as exc:
            raise APIError(
                status_code=503,
                code="auth_jwks_unavailable",
                detail="JWKS fetch failed.",
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

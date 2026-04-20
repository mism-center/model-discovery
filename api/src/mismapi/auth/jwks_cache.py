"""
Single-flight JWKS cache.

Fetches a JWKS document from a URI resolved at call time (via a supplier
callback so it works with both OIDC-discovery-derived URIs and statically
configured `JWT_JWKS_URL` ones), keyed by `kid`. Concurrent callers
converge on a single fetch via an `asyncio.Lock` and share the resulting
dictionary.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable

import httpx

from mismapi.core.errors import APIError

logger = logging.getLogger(__name__)

JWKSDict = dict[str, dict[str, object]]
JWKSUriSupplier = Callable[[], Awaitable[str]]


class JWKSCache:
    """Thread-safe, single-flight cache for a JWKS `kid -> key` mapping."""

    def __init__(
        self,
        *,
        uri_supplier: JWKSUriSupplier,
        ttl_seconds: int,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._uri_supplier = uri_supplier
        self._ttl_seconds = ttl_seconds
        self._http_client = http_client
        self._owns_client = http_client is None
        self._cache: JWKSDict = {}
        self._cached_at: float = 0.0
        self._lock = asyncio.Lock()

    @classmethod
    def from_keys(
        cls,
        keys: JWKSDict,
        *,
        uri: str = "test://jwks",
        ttl_seconds: int = 300,
    ) -> JWKSCache:
        """Construct a cache pre-seeded with keys. Intended for tests."""

        async def _uri() -> str:
            return uri

        cache = cls(uri_supplier=_uri, ttl_seconds=ttl_seconds)
        cache.seed(keys)
        return cache

    def seed(self, keys: JWKSDict) -> None:
        self._cache = dict(keys)
        self._cached_at = time.time()

    async def invalidate(self) -> None:
        async with self._lock:
            self._cache = {}
            self._cached_at = 0.0

    async def get(self) -> JWKSDict:
        if self._is_fresh():
            return self._cache

        async with self._lock:
            if self._is_fresh():
                return self._cache

            parsed = await self._fetch()
            self._cache = parsed
            self._cached_at = time.time()
            return parsed

    def _is_fresh(self) -> bool:
        if not self._cache:
            return False
        return (time.time() - self._cached_at) < self._ttl_seconds

    async def _fetch(self) -> JWKSDict:
        jwks_uri = await self._uri_supplier()
        if not jwks_uri:
            raise APIError(
                status_code=500,
                code="auth_oidc_uninitialized",
                detail="JWKS URI is not configured.",
            )

        logger.info("refreshing_jwks url=%s", jwks_uri)

        client = self._http_client or httpx.AsyncClient(timeout=10.0)
        try:
            try:
                response = await client.get(jwks_uri)
                response.raise_for_status()
                payload = response.json()
            except httpx.HTTPError as exc:
                raise APIError(
                    status_code=503,
                    code="auth_jwks_unavailable",
                    detail="JWKS fetch failed.",
                ) from exc
        finally:
            if self._owns_client:
                await client.aclose()

        keys_raw = payload.get("keys")
        if not isinstance(keys_raw, list):
            raise APIError(
                status_code=503,
                code="auth_jwks_invalid",
                detail="JWKS response is invalid.",
            )

        parsed: JWKSDict = {}
        for key_item in keys_raw:
            if not isinstance(key_item, dict):
                continue
            kid = key_item.get("kid")
            if isinstance(kid, str) and kid:
                parsed[kid] = key_item
        return parsed

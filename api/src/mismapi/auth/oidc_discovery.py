"""
Single-flight OIDC discovery cache.

One cache per app. Concurrent `get()` callers during a cold start (or TTL
expiry) converge on a single underlying fetch via an `asyncio.Lock`. The
losers await the winner's result rather than racing an independent HTTP call.
"""

from __future__ import annotations

import asyncio
import logging
import time

import httpx

from mismapi.auth.oidc_types import OIDCDiscoveryDocument
from mismapi.core.errors import APIError
from mismapi.core.settings import Settings

logger = logging.getLogger(__name__)


class OIDCDiscoveryCache:
    """Thread-safe, single-flight cache for the OIDC discovery document."""

    def __init__(
        self,
        settings: Settings,
        *,
        http_client: httpx.AsyncClient | None = None,
        ttl_seconds: int | None = None,
    ) -> None:
        self._settings = settings
        self._http_client = http_client
        self._owns_client = http_client is None
        self._ttl_seconds = ttl_seconds
        self._cached: OIDCDiscoveryDocument | None = None
        self._cached_at: float = 0.0
        self._lock = asyncio.Lock()

    @property
    def cached(self) -> OIDCDiscoveryDocument | None:
        """Currently cached document, if any. Does not trigger a fetch."""
        return self._cached

    def seed(self, document: OIDCDiscoveryDocument) -> None:
        """Install a document directly. Intended for tests and container priming."""
        self._cached = document
        self._cached_at = time.time()

    async def invalidate(self) -> None:
        async with self._lock:
            self._cached = None
            self._cached_at = 0.0

    async def get(self) -> OIDCDiscoveryDocument:
        if self._is_fresh():
            assert self._cached is not None
            return self._cached

        async with self._lock:
            if self._is_fresh():
                assert self._cached is not None
                return self._cached

            document = await self._fetch()
            self._cached = document
            self._cached_at = time.time()
            return document

    def _is_fresh(self) -> bool:
        if self._cached is None:
            return False
        if self._ttl_seconds is None:
            return True
        return (time.time() - self._cached_at) < self._ttl_seconds

    async def _fetch(self) -> OIDCDiscoveryDocument:
        discovery_url = self._get_discovery_url()
        logger.info("loading_oidc_discovery url=%s", discovery_url)

        client = self._http_client or httpx.AsyncClient(timeout=10.0)
        try:
            try:
                response = await client.get(discovery_url)
                response.raise_for_status()
                payload = response.json()
            except httpx.HTTPError as exc:
                raise APIError(
                    status_code=503,
                    code="auth_oidc_discovery_unavailable",
                    detail="OIDC discovery fetch failed.",
                ) from exc
        finally:
            if self._owns_client:
                await client.aclose()

        issuer = payload.get("issuer")
        authorization_endpoint = payload.get("authorization_endpoint")
        token_endpoint = payload.get("token_endpoint")
        jwks_uri = payload.get("jwks_uri")
        end_session_endpoint = payload.get("end_session_endpoint", "")

        if (
            not isinstance(issuer, str)
            or not isinstance(authorization_endpoint, str)
            or not isinstance(token_endpoint, str)
            or not isinstance(jwks_uri, str)
        ):
            raise APIError(
                status_code=503,
                code="auth_oidc_discovery_invalid",
                detail="OIDC discovery payload is missing required fields.",
            )

        end_session = end_session_endpoint if isinstance(end_session_endpoint, str) else ""
        return OIDCDiscoveryDocument(
            issuer=issuer,
            authorization_endpoint=authorization_endpoint,
            token_endpoint=token_endpoint,
            jwks_uri=jwks_uri,
            end_session_endpoint=end_session,
        )

    def _get_discovery_url(self) -> str:
        """Return the effective discovery URL for the configured IdP."""
        if self._settings.oidc_discovery_url:
            return self._settings.oidc_discovery_url
        issuer = self._settings.oidc_issuer_url.rstrip("/")
        return f"{issuer}/.well-known/openid-configuration"

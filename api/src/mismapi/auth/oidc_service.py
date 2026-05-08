"""
OIDC flow facade backed by an Authlib Starlette OAuth client.

Wraps `StarletteOAuth2App` so handlers and the session refresher get a single
async-friendly interface.

This module owns only the error mapping and the small bits Authlib does not
cover directly (RP-initiated logout URL construction, normalizing
`expires_in`, exposing the validated `userinfo` dict on `TokenResponse`).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, NoReturn
from urllib.parse import urlencode

import httpx
from authlib.integrations.base_client.errors import MismatchingStateError, OAuthError
from pydantic import ValidationError
from starlette.responses import RedirectResponse

from mismapi.auth.oidc_types import (
    CODE_EXCHANGE_ERRORS,
    REFRESH_ERRORS,
    TOKEN_ERROR_BODY_MAX_LEN,
    IdpServerMetadata,
    OIDCErrorCodes,
    TokenResponse,
)
from mismapi.core.errors import APIError
from mismapi.core.settings import Settings
from mismapi.utils import get_string_or_empty_from_dict

if TYPE_CHECKING:
    from authlib.integrations.starlette_client import StarletteOAuth2App
    from starlette.requests import Request

logger = logging.getLogger(__name__)


def _normalize_expires_in_to_seconds(value: object) -> int:
    """
    Normalize an OAuth `expires_in` JSON value into a non-negative int of seconds.

    Tolerates junk input (wrong types, unparsable strings, NaN, negatives) by
    returning `0`, so callers can treat `0` as "already expired / no
    useful lifetime" rather than having to wrap every access in try/except.
    """
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        try:
            n = int(value)
        except (ValueError, OverflowError):
            return 0
        return n if n > 0 else 0
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return 0
        try:
            n = int(s)
        except ValueError:
            return 0
        return n if n > 0 else 0
    return 0


def _build_token_response(
    token: dict[str, object],
    *,
    invalid_access_token_code: str = "auth_token_exchange_invalid",
) -> TokenResponse:
    access_token = token.get("access_token")
    if not isinstance(access_token, str) or not access_token.strip():
        raise APIError(
            status_code=502,
            code=invalid_access_token_code,
            detail="OIDC token response is missing or empty access_token.",
        )
    id_token = get_string_or_empty_from_dict(token, "id_token")
    refresh_out = get_string_or_empty_from_dict(token, "refresh_token")
    expires_in = _normalize_expires_in_to_seconds(token.get("expires_in", 0))
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_out,
        id_token=id_token,
        expires_in=expires_in,
    )


def _raise_for_http_error(
    log_event: str,
    codes: OIDCErrorCodes,
    exc: httpx.HTTPError,
) -> NoReturn:
    if isinstance(exc, httpx.HTTPStatusError):
        body_text = exc.response.text or ""
        body_prefix = body_text[:TOKEN_ERROR_BODY_MAX_LEN]
        logger.error(
            "%s status=%s body_prefix=%s",
            log_event,
            exc.response.status_code,
            body_prefix,
        )
        raise APIError(
            status_code=502,
            code=codes.http_status_failed,
            detail=codes.detail_failed,
        ) from exc

    raise APIError(
        status_code=502,
        code=codes.unavailable,
        detail=codes.detail_unavailable,
    ) from exc


def _raise_oauth_error(
    log_event: str,
    codes: OIDCErrorCodes,
    exc: OAuthError,
) -> NoReturn:
    logger.error(
        "%s oauth_error=%s description=%s",
        log_event,
        getattr(exc, "error", type(exc).__name__),
        str(getattr(exc, "description", ""))[:TOKEN_ERROR_BODY_MAX_LEN],
    )
    raise APIError(
        status_code=502,
        code=codes.http_status_failed,
        detail=codes.detail_failed,
    ) from exc


class OIDCService:
    """All OIDC flows, delegated to an Authlib `StarletteOAuth2App`.

    The client is resolved once from the OAuth registry at container-build
    time and passed in, so per-request methods don't pay the registry-lookup
    cost on every call.
    """

    def __init__(self, *, settings: Settings, client: StarletteOAuth2App) -> None:
        self._settings = settings
        self._client = client

    async def authorize_redirect(self, request: Request) -> RedirectResponse:
        return await self._client.authorize_redirect(
            request,
            self._settings.oidc_redirect_uri,
        )

    async def authorize_access_token(self, request: Request) -> TokenResponse:
        """
        Validate state, exchange the authorization code, and validate the ID
        token. Returns the parsed token plus validated `userinfo` claims.

        `MismatchingStateError` is intentionally **not** caught here.
        Handlers map it to a redirect-to-login so an expired or replayed state
        cookie produces a graceful re-auth instead of a 4xx.
        """
        try:
            token = await self._client.authorize_access_token(request)
        except MismatchingStateError:
            raise
        except OAuthError as exc:
            _raise_oauth_error("oidc_token_exchange_failed", CODE_EXCHANGE_ERRORS, exc)
        except httpx.HTTPError as exc:
            _raise_for_http_error(
                "oidc_token_exchange_failed",
                CODE_EXCHANGE_ERRORS,
                exc,
            )

        if not isinstance(token, dict):
            raise APIError(
                status_code=502,
                code=CODE_EXCHANGE_ERRORS.invalid_response,
                detail="OIDC token response is malformed.",
            )

        id_token = token.get("id_token")
        if not isinstance(id_token, str) or not id_token:
            raise APIError(
                status_code=502,
                code=CODE_EXCHANGE_ERRORS.invalid_response,
                detail="OIDC token response is missing required fields.",
            )
        return _build_token_response(dict(token))

    async def refresh(self, *, refresh_token: str) -> TokenResponse:
        try:
            token = await self._client.fetch_access_token(
                grant_type="refresh_token",
                refresh_token=refresh_token,
            )
        except OAuthError as exc:
            _raise_oauth_error("oidc_token_refresh_failed", REFRESH_ERRORS, exc)
        except httpx.HTTPError as exc:
            _raise_for_http_error(
                "oidc_token_refresh_failed",
                REFRESH_ERRORS,
                exc,
            )

        return _build_token_response(
            dict(token),
            invalid_access_token_code=REFRESH_ERRORS.invalid_response,
        )

    async def load_metadata(self) -> IdpServerMetadata:
        """
        Fetch and validate the OIDC discovery document.

        Authlib caches the raw payload internally for the lifetime of the
        client (no TTL); this method re-validates the cached payload through
        `IdpServerMetadata` on every call so all downstream consumers get a
        typed, shape-checked document instead of an untyped `dict[str, Any]`.

        Validation cost is bounded — the underlying HTTP fetch only happens
        on the first call.
        """
        raw = await self._client.load_server_metadata()
        try:
            return IdpServerMetadata.model_validate(raw)
        except ValidationError as exc:
            logger.error("oidc_discovery_invalid errors=%s", exc.errors())
            raise APIError(
                status_code=503,
                code="auth_oidc_discovery_invalid",
                detail="OIDC discovery payload failed validation.",
            ) from exc

    async def build_end_session_url(self, *, id_token_hint: str) -> str | None:
        """
        Build the RP-initiated logout URL from the cached server metadata.

        Returns `None` when the provider does not advertise an end-session
        endpoint, so the handler can fall back to a plain JSON logout.
        """
        metadata = await self.load_metadata()
        if not metadata.end_session_endpoint:
            return None
        params: dict[str, str] = {
            "id_token_hint": id_token_hint,
            "client_id": self._settings.oidc_client_id,
        }
        if self._settings.oidc_post_logout_redirect_uri:
            params["post_logout_redirect_uri"] = self._settings.oidc_post_logout_redirect_uri
        return f"{metadata.end_session_endpoint}?{urlencode(params)}"

    async def load_jwks_uri(self) -> str:
        """Return the JWKS URI from validated server metadata, for the inbound validator."""
        metadata = await self.load_metadata()
        return metadata.jwks_uri

    async def load_issuer(self) -> str:
        """Return the issuer claim from validated server metadata."""
        metadata = await self.load_metadata()
        return metadata.issuer

    async def prime_metadata(self) -> None:
        """Best-effort warm-up of the server metadata cache (with validation)."""
        await self.load_metadata()


__all__ = [
    "OIDCService",
    "_normalize_expires_in_to_seconds",
    "_build_token_response",
]

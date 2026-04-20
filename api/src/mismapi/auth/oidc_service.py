"""
Unified OIDC flow service.

Single entry point for every OIDC flow the API performs: building the
authorization URL, exchanging an authorization code, refreshing tokens,
and constructing the end-session URL.

The service owns **one** long-lived `AsyncOAuth2Client`. All flows are
issued through that client, keeping the connection pool warm and removing the
per-call client construction churn that plagued the old free-function API.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, NoReturn
from urllib.parse import urlencode

import httpx
from authlib.integrations.base_client.errors import OAuthError
from authlib.integrations.httpx_client import AsyncOAuth2Client
from authlib.oauth2.rfc6749.errors import MismatchingStateException

from mismapi.auth.oidc_types import (
    CODE_EXCHANGE_ERRORS,
    REFRESH_ERRORS,
    TOKEN_ERROR_BODY_MAX_LEN,
    OIDCErrorCodes,
    TokenResponse,
)
from mismapi.core.errors import APIError
from mismapi.core.settings import Settings
from mismapi.utils import get_string_or_empty_from_dict

if TYPE_CHECKING:
    from mismapi.auth.oidc_discovery import OIDCDiscoveryCache

logger = logging.getLogger(__name__)


def _build_authorization_callback_url(settings: Settings, *, code: str, state: str) -> str:
    return f"{settings.oidc_redirect_uri}?{urlencode({'code': code, 'state': state})}"


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


def _build_authlib_token_response(
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
    """All OIDC flows, backed by a single long-lived authlib client."""

    def __init__(
        self,
        *,
        settings: Settings,
        discovery: OIDCDiscoveryCache,
    ) -> None:
        self._settings = settings
        self._discovery = discovery
        self._client = AsyncOAuth2Client(
            client_id=settings.oidc_client_id,
            client_secret=settings.oidc_client_secret,
            redirect_uri=settings.oidc_redirect_uri,
            scope="openid",
            code_challenge_method="S256",
            token_endpoint_auth_method="client_secret_post",
            timeout=httpx.Timeout(15.0),
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def build_authorization_url(self, *, state: str, code_verifier: str) -> str:
        discovery = await self._discovery.get()
        url, _ = self._client.create_authorization_url(
            discovery.authorization_endpoint,
            state=state,
            code_verifier=code_verifier,
        )
        return url

    async def exchange_code(
        self,
        *,
        code: str,
        code_verifier: str,
        state: str,
    ) -> TokenResponse:
        discovery = await self._discovery.get()
        try:
            token = await self._client.fetch_token(
                discovery.token_endpoint,
                authorization_response=_build_authorization_callback_url(
                    self._settings,
                    code=code,
                    state=state,
                ),
                code_verifier=code_verifier,
                state=state,
            )
        except MismatchingStateException as exc:
            logger.warning("oidc_mismatching_state error=%s", exc)
            raise APIError(
                status_code=400,
                code="auth_callback_invalid",
                detail="OAuth state did not match.",
            ) from exc
        except OAuthError as exc:
            _raise_oauth_error("oidc_token_exchange_failed", CODE_EXCHANGE_ERRORS, exc)
        except httpx.HTTPError as exc:
            _raise_for_http_error(
                "oidc_token_exchange_failed",
                CODE_EXCHANGE_ERRORS,
                exc,
            )

        id_token = token.get("id_token")
        if not isinstance(id_token, str) or not id_token:
            raise APIError(
                status_code=502,
                code=CODE_EXCHANGE_ERRORS.invalid_response,
                detail="OIDC token response is missing required fields.",
            )
        return _build_authlib_token_response(dict(token))

    async def refresh(self, *, refresh_token: str) -> TokenResponse:
        discovery = await self._discovery.get()
        try:
            token = await self._client.refresh_token(
                discovery.token_endpoint,
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

        return _build_authlib_token_response(
            dict(token),
            invalid_access_token_code=REFRESH_ERRORS.invalid_response,
        )

    async def build_end_session_url(self, *, id_token_hint: str) -> str:
        discovery = await self._discovery.get()
        if not discovery.end_session_endpoint:
            raise APIError(
                status_code=503,
                code="auth_end_session_unavailable",
                detail="OIDC provider does not advertise an end_session_endpoint.",
            )
        params: dict[str, str] = {
            "id_token_hint": id_token_hint,
            "client_id": self._settings.oidc_client_id,
        }
        if self._settings.oidc_post_logout_redirect_uri:
            params["post_logout_redirect_uri"] = self._settings.oidc_post_logout_redirect_uri
        return f"{discovery.end_session_endpoint}?{urlencode(params)}"

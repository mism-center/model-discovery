import logging
import secrets
from dataclasses import dataclass, field
from urllib.parse import urlencode

import httpx
from authlib.integrations.base_client.errors import OAuthError
from authlib.integrations.httpx_client import AsyncOAuth2Client
from authlib.oauth2.rfc6749.errors import MismatchingStateException

from mismapi.core.errors import APIError
from mismapi.core.settings import Settings
from mismapi.utils import get_string_or_empty_from_dict

logger = logging.getLogger(__name__)

TOKEN_ERROR_BODY_MAX_LEN = 256

TOKEN_EXCHANGE_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:token-exchange"
JWT_ACCESS_TOKEN_TYPE = "urn:ietf:params:oauth:token-type:access_token"


@dataclass(frozen=True, slots=True)
class ExchangedAccessTokenResult:
    access_token: str
    issued_token_type: str
    expires_in: int


@dataclass(frozen=True, slots=True)
class OIDCDiscoveryDocument:
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str
    end_session_endpoint: str

    def build_end_session_url(self, settings: Settings, *, id_token_hint: str) -> str:
        params: dict[str, str] = {
            "id_token_hint": id_token_hint,
            "client_id": settings.oidc_client_id,
        }
        if settings.oidc_post_logout_redirect_uri:
            params["post_logout_redirect_uri"] = settings.oidc_post_logout_redirect_uri
        return f"{self.end_session_endpoint}?{urlencode(params)}"


@dataclass(frozen=True, slots=True)
class TokenResponse:
    access_token: str
    refresh_token: str
    id_token: str
    expires_in: int


def _discovery_url(settings: Settings) -> str:
    if settings.oidc_discovery_url:
        return settings.oidc_discovery_url
    issuer = settings.oidc_issuer_url.rstrip("/")
    return f"{issuer}/.well-known/openid-configuration"


def _build_async_oauth_client(
    discovery: OIDCDiscoveryDocument,
    settings: Settings,
) -> AsyncOAuth2Client:
    return AsyncOAuth2Client(
        client_id=settings.oidc_client_id,
        client_secret=settings.oidc_client_secret,
        redirect_uri=settings.oidc_redirect_uri,
        scope="openid",
        code_challenge_method="S256",
        token_endpoint_auth_method="client_secret_post",
        timeout=httpx.Timeout(10.0),
        issuer=discovery.issuer,
        authorization_endpoint=discovery.authorization_endpoint,
        token_endpoint=discovery.token_endpoint,
    )


def _build_token_exchange_oauth_client(
    discovery: OIDCDiscoveryDocument,
    settings: Settings,
) -> AsyncOAuth2Client:
    """OAuth client for token-endpoint exchange only (no default OIDC scopes on the request)."""
    return AsyncOAuth2Client(
        client_id=settings.oidc_client_id,
        client_secret=settings.oidc_client_secret,
        token_endpoint_auth_method="client_secret_post",
        timeout=httpx.Timeout(15.0),
        issuer=discovery.issuer,
        token_endpoint=discovery.token_endpoint,
        scope=None,
    )


def _coerce_expires_in(value: object) -> int:
    """Normalize OAuth ``expires_in`` to a non-negative int seconds."""
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
    expires_in = _coerce_expires_in(token.get("expires_in", 0))
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_out,
        id_token=id_token,
        expires_in=expires_in,
    )


def _map_oauth_http_errors(prefix: str, exc: Exception) -> None:
    if isinstance(exc, httpx.HTTPStatusError):
        body_text = exc.response.text or ""
        body_prefix = body_text[:TOKEN_ERROR_BODY_MAX_LEN]
        logger.error("%s status=%s body_prefix=%s", prefix, exc.response.status_code, body_prefix)
        is_exchange = "exchange" in prefix
        raise APIError(
            status_code=502,
            code="auth_token_exchange_failed" if is_exchange else "auth_token_refresh_failed",
            detail="OIDC token exchange failed." if is_exchange else "OIDC token refresh failed.",
        ) from exc
    if isinstance(exc, httpx.HTTPError):
        is_exchange = "exchange" in prefix
        raise APIError(
            status_code=502,
            code="auth_token_exchange_unavailable"
            if is_exchange
            else "auth_token_refresh_unavailable",
            detail="OIDC token endpoint is unavailable.",
        ) from exc


@dataclass(slots=True)
class OIDCDiscoveryLoader:
    """OIDC discovery and OAuth2 flows via Authlib AsyncOAuth2Client."""

    settings: Settings
    _cached: OIDCDiscoveryDocument | None = field(default=None)

    async def load(self) -> OIDCDiscoveryDocument:
        if self._cached is not None:
            return self._cached

        discovery_url = _discovery_url(self.settings)
        logger.info("loading_oidc_discovery url=%s", discovery_url)
        try:
            async with AsyncOAuth2Client(
                client_id=self.settings.oidc_client_id,
                client_secret=self.settings.oidc_client_secret,
                token_endpoint_auth_method="client_secret_post",
                timeout=httpx.Timeout(10.0),
            ) as client:
                response = await client.request(
                    "GET",
                    discovery_url,
                    withhold_token=True,
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError as exc:
            raise APIError(
                status_code=503,
                code="auth_oidc_discovery_unavailable",
                detail="OIDC discovery fetch failed.",
            ) from exc

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
        self._cached = OIDCDiscoveryDocument(
            issuer=issuer,
            authorization_endpoint=authorization_endpoint,
            token_endpoint=token_endpoint,
            jwks_uri=jwks_uri,
            end_session_endpoint=end_session,
        )
        return self._cached

    async def create_authorization_url(self, *, state: str, code_verifier: str) -> str:
        discovery = await self.load()
        client = _build_async_oauth_client(discovery, self.settings)
        try:
            url, _ = client.create_authorization_url(
                discovery.authorization_endpoint,
                state=state,
                code_verifier=code_verifier,
            )
        finally:
            await client.aclose()
        return url


def generate_code_verifier() -> str:
    """PKCE ``code_verifier`` (high-entropy secret)."""
    return secrets.token_urlsafe(96)


def build_authorization_callback_url(settings: Settings, *, code: str, state: str) -> str:
    return f"{settings.oidc_redirect_uri}?{urlencode({'code': code, 'state': state})}"


async def exchange_code_for_tokens(
    discovery: OIDCDiscoveryDocument,
    settings: Settings,
    code: str,
    code_verifier: str,
    *,
    state: str,
) -> TokenResponse:
    client = _build_async_oauth_client(discovery, settings)
    token: dict[str, object] | None = None
    try:
        token = await client.fetch_token(
            discovery.token_endpoint,
            authorization_response=build_authorization_callback_url(
                settings,
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
        logger.error(
            "oidc_token_exchange_failed oauth_error=%s description=%s",
            getattr(exc, "error", type(exc).__name__),
            str(getattr(exc, "description", ""))[:TOKEN_ERROR_BODY_MAX_LEN],
        )
        raise APIError(
            status_code=502,
            code="auth_token_exchange_failed",
            detail="OIDC token exchange failed.",
        ) from exc
    except httpx.HTTPStatusError as exc:
        _map_oauth_http_errors("oidc_token_exchange_failed", exc)
    except httpx.HTTPError as exc:
        _map_oauth_http_errors("oidc_token_exchange_failed", exc)
    finally:
        await client.aclose()

    if token is None:
        raise APIError(
            status_code=502,
            code="auth_token_exchange_failed",
            detail="OIDC token exchange failed.",
        )
    id_token = token.get("id_token")
    if not isinstance(id_token, str) or not id_token:
        raise APIError(
            status_code=502,
            code="auth_token_exchange_invalid",
            detail="OIDC token response is missing required fields.",
        )
    return _build_authlib_token_response(dict(token))


async def refresh_tokens(
    discovery: OIDCDiscoveryDocument,
    settings: Settings,
    *,
    refresh_token: str,
) -> TokenResponse:
    client = _build_async_oauth_client(discovery, settings)
    token: dict[str, object] | None = None
    try:
        token = await client.refresh_token(
            discovery.token_endpoint,
            refresh_token=refresh_token,
        )
    except OAuthError as exc:
        logger.error(
            "oidc_token_refresh_failed oauth_error=%s description=%s",
            getattr(exc, "error", type(exc).__name__),
            str(getattr(exc, "description", ""))[:TOKEN_ERROR_BODY_MAX_LEN],
        )
        raise APIError(
            status_code=502,
            code="auth_token_refresh_failed",
            detail="OIDC token refresh failed.",
        ) from exc
    except httpx.HTTPStatusError as exc:
        _map_oauth_http_errors("oidc_token_refresh_failed", exc)
    except httpx.HTTPError as exc:
        _map_oauth_http_errors("oidc_token_refresh_failed", exc)
    finally:
        await client.aclose()

    if token is None:
        raise APIError(
            status_code=502,
            code="auth_token_refresh_failed",
            detail="OIDC token refresh failed.",
        )
    return _build_authlib_token_response(
        dict(token),
        invalid_access_token_code="auth_token_refresh_invalid",
    )


async def exchange_access_token_for_audience(
    discovery: OIDCDiscoveryDocument,
    settings: Settings,
    *,
    subject_access_token: str,
    audience: str,
) -> ExchangedAccessTokenResult:
    """
    Token exchange at the IdP token endpoint (e.g. Keycloak standard token exchange).

    The IdP must allow OIDC_CLIENT_ID to exchange a user access token into the given audience.
    """
    if not audience.strip():
        raise APIError(
            status_code=500,
            code="auth_token_upstream_audience_missing",
            detail="Token exchange audience is not configured.",
        )

    fetch_kwargs: dict[str, str] = {
        "subject_token": subject_access_token,
        "subject_token_type": JWT_ACCESS_TOKEN_TYPE,
        "audience": audience.strip(),
        "requested_token_type": JWT_ACCESS_TOKEN_TYPE,
    }
    scope_parts = settings.oidc_token_exchange_scopes_parts
    if scope_parts:
        fetch_kwargs["scope"] = " ".join(scope_parts)

    client = _build_token_exchange_oauth_client(discovery, settings)
    token: dict[str, object] | None = None
    try:
        token = await client.fetch_token(
            discovery.token_endpoint,
            grant_type=TOKEN_EXCHANGE_GRANT_TYPE,
            **fetch_kwargs,
        )
    except OAuthError as exc:
        logger.error(
            "oidc_upstream_token_exchange_oauth_error oauth_error=%s description=%s",
            getattr(exc, "error", type(exc).__name__),
            str(getattr(exc, "description", ""))[:TOKEN_ERROR_BODY_MAX_LEN],
        )
        raise APIError(
            status_code=502,
            code="auth_token_exchange_failed",
            detail="OIDC token exchange failed.",
        ) from exc
    except httpx.HTTPStatusError as exc:
        _map_oauth_http_errors("oidc_upstream_token_exchange_http", exc)
    except httpx.HTTPError as exc:
        _map_oauth_http_errors("oidc_upstream_token_exchange_http", exc)
    finally:
        await client.aclose()

    if token is None:
        raise APIError(
            status_code=502,
            code="auth_token_exchange_response_invalid",
            detail="Token exchange returned no token payload.",
        )

    body: dict[str, object] = dict(token)

    issued_raw = get_string_or_empty_from_dict(body, "issued_token_type").strip()
    if issued_raw != JWT_ACCESS_TOKEN_TYPE:
        logger.warning(
            "oidc_upstream_unexpected_issued_token_type issued_token_type=%s",
            issued_raw,
        )
        raise APIError(
            status_code=502,
            code="auth_token_exchange_issued_type_mismatch",
            detail="Token exchange did not return an access token type.",
        )

    access_token = get_string_or_empty_from_dict(body, "access_token").strip()
    if not access_token:
        raise APIError(
            status_code=502,
            code="auth_token_exchange_missing_access_token",
            detail="Token exchange response is missing access_token.",
        )

    expires_in = _coerce_expires_in(body.get("expires_in", 0))
    return ExchangedAccessTokenResult(
        access_token=access_token,
        issued_token_type=issued_raw,
        expires_in=expires_in,
    )

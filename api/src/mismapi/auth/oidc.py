import hashlib
import logging
import secrets
from base64 import urlsafe_b64encode
from dataclasses import dataclass, field
from urllib.parse import urlencode

import httpx

from mismapi.core.errors import APIError
from mismapi.core.settings import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class OIDCDiscoveryDocument:
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str
    end_session_endpoint: str


@dataclass(frozen=True, slots=True)
class TokenResponse:
    access_token: str
    refresh_token: str
    id_token: str
    expires_in: int


@dataclass(slots=True)
class OIDCDiscoveryLoader:
    """Fetches and caches the OpenID Connect discovery document."""

    settings: Settings
    _cached: OIDCDiscoveryDocument | None = field(default=None)

    async def load(self) -> OIDCDiscoveryDocument:
        if self._cached is not None:
            return self._cached

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


def generate_pkce_pair() -> tuple[str, str]:
    code_verifier = secrets.token_urlsafe(96)
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return code_verifier, code_challenge


def build_authorize_url(
    discovery: OIDCDiscoveryDocument,
    settings: Settings,
    state: str,
    code_challenge: str,
) -> str:
    params = {
        "response_type": "code",
        "client_id": settings.oidc_client_id,
        "redirect_uri": settings.oidc_redirect_uri,
        "scope": "openid",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{discovery.authorization_endpoint}?{urlencode(params)}"


async def exchange_code_for_tokens(
    discovery: OIDCDiscoveryDocument,
    settings: Settings,
    code: str,
    code_verifier: str,
) -> TokenResponse:
    form_data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.oidc_redirect_uri,
        "client_id": settings.oidc_client_id,
        "client_secret": settings.oidc_client_secret,
        "code_verifier": code_verifier,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                discovery.token_endpoint,
                data=form_data,
            )
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPStatusError as exc:
        logger.error(
            "oidc_token_exchange_failed status=%s body=%s",
            exc.response.status_code,
            exc.response.text,
        )
        raise APIError(
            status_code=502,
            code="auth_token_exchange_failed",
            detail="OIDC token exchange failed.",
        ) from exc
    except httpx.HTTPError as exc:
        raise APIError(
            status_code=502,
            code="auth_token_exchange_unavailable",
            detail="OIDC token endpoint is unavailable.",
        ) from exc

    access_token = payload.get("access_token")
    id_token = payload.get("id_token")
    if not isinstance(access_token, str) or not isinstance(id_token, str):
        raise APIError(
            status_code=502,
            code="auth_token_exchange_invalid",
            detail="OIDC token response is missing required fields.",
        )

    return TokenResponse(
        access_token=access_token,
        refresh_token=payload.get("refresh_token", ""),
        id_token=id_token,
        expires_in=int(payload.get("expires_in", 0)),
    )

import logging
import time
from dataclasses import dataclass
from typing import Protocol

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from mismapi.auth.oidc import OIDCDiscoveryLoader, refresh_tokens
from mismapi.core.errors import APIError
from mismapi.core.settings import Settings

logger = logging.getLogger(__name__)

bearer_scheme = HTTPBearer(auto_error=False)
bearer_dependency = Depends(bearer_scheme)


@dataclass(slots=True)
class AuthenticatedPrincipal:
    subject: str
    issuer: str
    audience: str
    scopes: set[str]


class AuthValidator(Protocol):
    async def validate_token(self, token: str) -> AuthenticatedPrincipal:
        raise NotImplementedError


def build_auth_validator(settings: Settings) -> AuthValidator:
    if settings.auth_mode == "oidc":
        from mismapi.auth.oidc_auth_validator import OIDCAuthValidator

        return OIDCAuthValidator(settings=settings)

    from mismapi.auth.jwt_auth_validator import JWTAuthValidator

    return JWTAuthValidator(settings=settings)


async def require_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = bearer_dependency,
) -> AuthenticatedPrincipal:
    if credentials is not None and credentials.scheme.lower() == "bearer":
        validator: AuthValidator = request.app.state.auth_validator
        return await validator.validate_token(credentials.credentials)

    return await _principal_from_session_cookie(request)


async def _principal_from_session_cookie(request: Request) -> AuthenticatedPrincipal:
    from mismapi.auth.session import SessionStore

    settings: Settings = request.app.state.settings
    session_store: SessionStore | None = getattr(request.app.state, "session_store", None)

    if session_store is None:
        raise APIError(status_code=401, code="auth_missing", detail="Missing credentials.")

    session_id = request.cookies.get(settings.session_cookie_name)
    if not session_id:
        raise APIError(status_code=401, code="auth_missing", detail="Missing credentials.")

    session_data = await session_store.get(session_id)
    if session_data is None:
        raise APIError(
            status_code=401,
            code="auth_session_expired",
            detail="Session has expired or is invalid.",
        )

    access_token = session_data.get("access_token", "")
    if not access_token:
        raise APIError(
            status_code=401,
            code="auth_session_invalid",
            detail="Session is missing access token.",
        )

    validator: AuthValidator = request.app.state.auth_validator
    try:
        return await validator.validate_token(access_token)
    except jwt.ExpiredSignatureError:
        if settings.auth_mode != "oidc":
            raise APIError(
                status_code=401,
                code="auth_session_expired",
                detail="Session token has expired.",
            ) from None
        refresh = session_data.get("refresh_token", "")
        if not refresh:
            raise APIError(
                status_code=401,
                code="auth_session_expired",
                detail="Session has expired or is invalid.",
            ) from None
        discovery_loader: OIDCDiscoveryLoader = request.app.state.oidc_discovery_loader
        discovery = await discovery_loader.load()
        try:
            token_response = await refresh_tokens(
                discovery,
                settings,
                refresh_token=refresh,
            )
        except APIError:
            raise APIError(
                status_code=401,
                code="auth_session_expired",
                detail="Session has expired or is invalid.",
            ) from None
        merged = {**session_data, "access_token": token_response.access_token}
        if token_response.refresh_token:
            merged["refresh_token"] = token_response.refresh_token
        if token_response.id_token:
            merged["id_token"] = token_response.id_token
        ttl_sec = (
            token_response.expires_in
            if token_response.expires_in > 0
            else settings.session_ttl_seconds
        )
        merged["expires_at"] = str(int(time.time()) + ttl_sec)
        await session_store.replace(session_id, merged)
        return await validator.validate_token(token_response.access_token)

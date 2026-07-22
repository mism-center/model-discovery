"""
FastAPI-level auth glue.

`AuthenticatedPrincipal` lives in `mismapi.auth.principal` (a pure,
dependency-free value type) and the `AuthValidator` protocol lives alongside
the OIDC validator (`OIDCAuthValidator`) in `mismapi.auth.validator`, so
validator implementations can import them without dragging in the
request-path helpers below. This module re-exports them so existing callers
keep working.

Session token refreshing logic lives in `mismapi.auth.session_refresh` as the
`SessionRefresher` collaborator.

What remains here is strictly request-path stuff:

* `bearer_token_from_request_header` — lightweight header parsing.
* `build_auth_validator` — the factory the container uses at startup to build the `AuthValidator`.
* `require_principal` — the default `Depends` authenticated routes use to validate the principal.
"""

from __future__ import annotations

import logging
from typing import Annotated

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from mismapi.auth.factory import build_auth_validator
from mismapi.auth.principal import AuthenticatedPrincipal
from mismapi.auth.session import SessionStore
from mismapi.auth.session_refresh import SessionRefresher
from mismapi.auth.validator import AuthValidator
from mismapi.core.deps import (
    AuthValidatorDep,
    SessionRefresherDep,
    SessionStoreDep,
    SettingsDep,
)
from mismapi.core.errors import APIError
from mismapi.core.settings import Settings

__all__ = [
    "AuthenticatedPrincipal",
    "AuthValidator",
    "bearer_token_from_request_header",
    "build_auth_validator",
    "optional_principal",
    "require_principal",
]

logger = logging.getLogger(__name__)

bearer_scheme = HTTPBearer(auto_error=False)
bearer_dependency = Depends(bearer_scheme)


def bearer_token_from_request_header(request: Request) -> str | None:
    auth = request.headers.get("Authorization")
    if not auth:
        return None
    parts = auth.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    return token or None


async def require_principal(
    request: Request,
    settings: SettingsDep,
    session_store: SessionStoreDep,
    validator: AuthValidatorDep,
    session_refresher: SessionRefresherDep,
    credentials: HTTPAuthorizationCredentials | None = bearer_dependency,
) -> AuthenticatedPrincipal:
    if settings.disable_auth:
        return AuthenticatedPrincipal(
            subject="anonymous",
            issuer="local",
            audience="local",
            scopes=set(),
        )

    if credentials is not None and credentials.scheme.lower() == "bearer":
        return await validator.validate_token(credentials.credentials)

    return await _principal_from_session_cookie(
        request,
        settings=settings,
        session_store=session_store,
        validator=validator,
        session_refresher=session_refresher,
    )


async def _principal_from_session_cookie(
    request: Request,
    *,
    settings: Settings,
    session_store: SessionStore,
    validator: AuthValidator,
    session_refresher: SessionRefresher,
) -> AuthenticatedPrincipal:
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

    access_token = session_data.access_token
    if not access_token:
        raise APIError(
            status_code=401,
            code="auth_session_invalid",
            detail="Session is missing access token.",
        )

    try:
        return await validator.validate_token(access_token)
    except jwt.ExpiredSignatureError:
        if settings.auth_mode != "oidc":
            raise APIError(
                status_code=401,
                code="auth_session_expired",
                detail="Session token has expired.",
            ) from None
        if not session_data.refresh_token:
            raise APIError(
                status_code=401,
                code="auth_session_expired",
                detail="Session has expired or is invalid.",
            ) from None
        try:
            merged = await session_refresher.refresh(
                session_id=session_id,
                session_data=session_data,
            )
        except APIError:
            raise APIError(
                status_code=401,
                code="auth_session_expired",
                detail="Session has expired or is invalid.",
            ) from None
        return await validator.validate_token(merged.access_token)


AuthenticatedPrincipalDep = Annotated[AuthenticatedPrincipal, Depends(require_principal)]


async def optional_principal(
    request: Request,
    settings: SettingsDep,
    session_store: SessionStoreDep,
    validator: AuthValidatorDep,
    session_refresher: SessionRefresherDep,
    credentials: HTTPAuthorizationCredentials | None = bearer_dependency,
) -> AuthenticatedPrincipal | None:
    """Like `require_principal`, but yields `None` for anonymous callers."""
    try:
        return await require_principal(
            request,
            settings,
            session_store,
            validator,
            session_refresher,
            credentials,
        )
    except APIError:
        return None


OptionalPrincipalDep = Annotated[AuthenticatedPrincipal | None, Depends(optional_principal)]

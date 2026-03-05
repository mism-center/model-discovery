from dataclasses import dataclass
from typing import Protocol

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from mism_api.core.errors import APIError
from mism_api.core.settings import Settings

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
        from mism_api.auth.oidc import OIDCAuthValidator

        return OIDCAuthValidator(settings=settings)

    from mism_api.auth.jwt import JWTAuthValidator

    return JWTAuthValidator(settings=settings)


async def require_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = bearer_dependency,
) -> AuthenticatedPrincipal:
    if credentials is None:
        raise APIError(status_code=401, code="auth_missing", detail="Missing bearer token.")

    if credentials.scheme.lower() != "bearer":
        raise APIError(status_code=401, code="auth_scheme_invalid", detail="Invalid auth scheme.")

    validator: AuthValidator = request.app.state.auth_validator
    return await validator.validate_token(credentials.credentials)

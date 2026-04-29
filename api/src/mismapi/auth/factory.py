"""
Validator factory used by the app container at startup.

Kept in its own module so neither the container nor request-path glue
(`mismapi.auth.base`) has to import the other at module-load time.
"""

from __future__ import annotations

from mismapi.auth.oidc_service import OIDCService
from mismapi.auth.validator import AuthValidator, OIDCAuthValidator
from mismapi.core.settings import Settings


def build_auth_validator(
    settings: Settings,
    *,
    oidc_service: OIDCService,
) -> AuthValidator:
    if settings.auth_mode == "oidc":
        return OIDCAuthValidator(
            settings=settings,
            issuer_loader=oidc_service.load_issuer,
            jwks_uri_loader=oidc_service.load_jwks_uri,
        )

    raise ValueError(f"Invalid auth mode: {settings.auth_mode}")

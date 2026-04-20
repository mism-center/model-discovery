"""
Validator factory used by the app container at startup.

Kept in its own module so neither the container nor request-path glue
(`mismapi.auth.base`) has to import the other at module-load time. The
previous arrangement required an inline `from ... import build_auth_validator`
inside `AppContainer.build` purely to dodge the import cycle; this
module removes the need for that.
"""

from __future__ import annotations

from mismapi.auth.oidc_discovery import OIDCDiscoveryCache
from mismapi.auth.validator import AuthValidator, JWTAuthValidator, OIDCAuthValidator
from mismapi.core.settings import Settings


def build_auth_validator(
    settings: Settings,
    *,
    discovery_cache: OIDCDiscoveryCache | None = None,
) -> AuthValidator:
    if settings.auth_mode == "oidc":
        cache = discovery_cache or OIDCDiscoveryCache(settings=settings)
        return OIDCAuthValidator(settings=settings, discovery_cache=cache)

    return JWTAuthValidator(settings=settings)

"""
Startup-time configuration validation.

Invoked from `AppContainer.build` so the process
refuses to start when required settings are missing, rather than limping along
and surfacing the misconfiguration as confusing request-time 5xxes (an empty
`OIDC_ISSUER_URL` becomes `/.well-known/openid-configuration` at first
discovery fetch, etc.).

Validations are additive: every missing field is collected and reported in a
single `OIDCConfigurationError` so operators get the full picture on first
boot instead of playing whack-a-mole one `raise` at a time.
"""

from __future__ import annotations

from mismapi.core.settings import Settings


class OIDCConfigurationError(ValueError):
    """
    Raised at startup when OIDC mode is selected but required settings are missing.

    Subclasses `ValueError` because the root cause is always an invalid
    configuration *value* (empty string where a real value is required).
    """


_REQUIRED_OIDC_FIELDS: tuple[tuple[str, str], ...] = (
    ("oidc_client_id", "OIDC_CLIENT_ID"),
    ("oidc_client_secret", "OIDC_CLIENT_SECRET"),
    ("oidc_audience", "OIDC_AUDIENCE"),
    ("oidc_redirect_uri", "OIDC_REDIRECT_URI"),
    ("oidc_cookie_signing_secret", "OIDC_COOKIE_SIGNING_SECRET"),
)


def ensure_startup_config(settings: Settings) -> None:
    """
    Validate cross-field settings constraints before app wiring.

    Validates OIDC-mode configuration. If in the future we add another auth
    mode or another mandatory integration, we will need to add different
    validation here.
    """
    if not settings.disable_auth:
        _ensure_oidc_config(settings)


def _ensure_oidc_config(settings: Settings) -> None:
    missing_env_names: list[str] = []

    for attribute_name, env_name in _REQUIRED_OIDC_FIELDS:
        value = getattr(settings, attribute_name, "")
        if not isinstance(value, str) or not value:
            missing_env_names.append(env_name)

    if not settings.oidc_issuer_url and not settings.oidc_discovery_url:
        missing_env_names.append("OIDC_ISSUER_URL or OIDC_DISCOVERY_URL")

    if not missing_env_names:
        return

    joined = ", ".join(missing_env_names)
    raise OIDCConfigurationError(
        "OIDC authentication is enabled but required OIDC configuration is missing or empty: "
        f"{joined}. Set these environment variables before starting the API."
    )

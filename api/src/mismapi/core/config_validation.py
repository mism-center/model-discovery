"""
Startup-time configuration validation.

Invoked from `AppContainer.build` so the process
refuses to start when required settings are missing, rather than limping along
and surfacing the misconfiguration as confusing request-time 5xxes (an empty
`OIDC_ISSUER_URL` becomes `/.well-known/openid-configuration` at first
discovery fetch, etc.).

Validations are additive: missing fields for each integration are collected
and reported together so operators get the full picture on first boot instead
of playing whack-a-mole one `raise` at a time.
"""

from __future__ import annotations

from urllib.parse import urlparse

from mismapi.core.settings import Settings


class StartupConfigurationError(ValueError):
    """Raised at startup when required configuration is missing or unsafe."""


class OIDCConfigurationError(StartupConfigurationError):
    """Raised when OIDC mode is selected but required settings are missing."""


class UploadConfigurationError(StartupConfigurationError):
    """Raised when production upload settings are missing or unsafe."""


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

    Validates OIDC-mode configuration and production-only upload safety
    settings. If in the future we add another auth mode or another mandatory
    integration, we will need to add different validation here.
    """
    if not settings.disable_auth:
        _ensure_oidc_config(settings)
    if settings.production_mode:
        _ensure_production_upload_config(settings)


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


def _ensure_production_upload_config(settings: Settings) -> None:
    missing_or_unsafe: list[str] = []

    if _is_local_url(settings.tusd_base_url):
        missing_or_unsafe.append("TUSD_BASE_URL")
    if not settings.tusd_hook_secret:
        missing_or_unsafe.append("TUSD_HOOK_SECRET")

    if not missing_or_unsafe:
        return

    joined = ", ".join(missing_or_unsafe)
    raise UploadConfigurationError(
        "Production mode is enabled but required upload configuration is missing or unsafe: "
        f"{joined}. Set these environment variables before starting the API."
    )


def _is_local_url(value: str) -> bool:
    if not value:
        return True
    hostname = urlparse(value).hostname
    return hostname in {"localhost", "127.0.0.1", "::1"}

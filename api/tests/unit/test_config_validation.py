from typing import Any

import pytest

from mismapi.core.config_validation import OIDCConfigurationError, ensure_startup_config
from mismapi.core.settings import Settings


def _settings(**overrides: Any) -> Settings:
    return Settings(_env_file=None, **overrides)  # type: ignore[call-arg]


def test_oidc_mode_reports_all_missing_fields_at_once() -> None:
    with pytest.raises(OIDCConfigurationError) as excinfo:
        ensure_startup_config(
            _settings(
                AUTH_MODE="oidc",
                OIDC_ISSUER_URL="",
                OIDC_DISCOVERY_URL="",
                OIDC_CLIENT_ID="",
                OIDC_CLIENT_SECRET="",
                OIDC_AUDIENCE="",
                OIDC_REDIRECT_URI="",
            )
        )

    message = str(excinfo.value)
    for name in (
        "OIDC_CLIENT_ID",
        "OIDC_CLIENT_SECRET",
        "OIDC_AUDIENCE",
        "OIDC_REDIRECT_URI",
        "OIDC_ISSUER_URL or OIDC_DISCOVERY_URL",
    ):
        assert name in message


def test_oidc_mode_accepts_discovery_url_in_lieu_of_issuer_url() -> None:
    ensure_startup_config(
        _settings(
            AUTH_MODE="oidc",
            OIDC_ISSUER_URL="",
            OIDC_DISCOVERY_URL="https://issuer.example.com/.well-known/openid-configuration",
            OIDC_CLIENT_ID="discovery-api",
            OIDC_CLIENT_SECRET="x",
            OIDC_AUDIENCE="discovery-api",
            OIDC_REDIRECT_URI="https://gateway.example.com/api/auth/callback",
        )
    )


def test_oidc_mode_rejects_whitespace_only_values() -> None:
    with pytest.raises(OIDCConfigurationError) as excinfo:
        ensure_startup_config(
            _settings(
                AUTH_MODE="oidc",
                OIDC_ISSUER_URL="https://issuer.example.com",
                OIDC_CLIENT_ID="   ",
                OIDC_CLIENT_SECRET="x",
                OIDC_AUDIENCE="discovery-api",
                OIDC_REDIRECT_URI="https://gateway.example.com/api/auth/callback",
            )
        )

    assert "OIDC_CLIENT_ID" in str(excinfo.value)

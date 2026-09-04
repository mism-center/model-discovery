from typing import Any

import pytest

from mismapi.core.config_validation import (
    OIDCConfigurationError,
    OpenFGAConfigurationError,
    UploadConfigurationError,
    ensure_startup_config,
)
from mismapi.core.settings import Settings
from tests.conftest import make_settings


def _settings(**overrides: Any) -> Settings:
    return make_settings(**overrides)


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
                OIDC_COOKIE_SIGNING_SECRET="",
            )
        )

    message = str(excinfo.value)
    for name in (
        "OIDC_CLIENT_ID",
        "OIDC_CLIENT_SECRET",
        "OIDC_AUDIENCE",
        "OIDC_REDIRECT_URI",
        "OIDC_COOKIE_SIGNING_SECRET",
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
            OIDC_COOKIE_SIGNING_SECRET="test-cookie-signing-secret",
            OPENFGA_STORE_ID="test-store",
        )
    )


def test_disable_auth_skips_oidc_validation() -> None:
    """`DISABLE_AUTH` skips OIDC validation entirely (no other required fields)."""
    ensure_startup_config(_settings(DISABLE_AUTH="true"))


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
                OIDC_COOKIE_SIGNING_SECRET="test-cookie-signing-secret",
            )
        )

    assert "OIDC_CLIENT_ID" in str(excinfo.value)


def test_production_mode_rejects_local_tusd_url() -> None:
    with pytest.raises(UploadConfigurationError) as excinfo:
        ensure_startup_config(
            _settings(
                DISABLE_AUTH="true",
                PRODUCTION_MODE="true",
                TUSD_BASE_URL="http://localhost:8080",
            )
        )

    assert "TUSD_BASE_URL" in str(excinfo.value)


def test_production_mode_accepts_external_tusd_url() -> None:
    ensure_startup_config(
        _settings(
            DISABLE_AUTH="true",
            PRODUCTION_MODE="true",
            TUSD_BASE_URL="https://uploads.example.com",
        )
    )


_VALID_OIDC_OVERRIDES: dict[str, Any] = {
    "AUTH_MODE": "oidc",
    "OIDC_ISSUER_URL": "https://issuer.example.com",
    "OIDC_CLIENT_ID": "discovery-api",
    "OIDC_CLIENT_SECRET": "x",
    "OIDC_AUDIENCE": "discovery-api",
    "OIDC_REDIRECT_URI": "https://gateway.example.com/api/auth/callback",
    "OIDC_COOKIE_SIGNING_SECRET": "test-cookie-signing-secret",
}


def test_openfga_requires_store_id_when_auth_enabled() -> None:
    with pytest.raises(OpenFGAConfigurationError) as excinfo:
        ensure_startup_config(_settings(**_VALID_OIDC_OVERRIDES, OPENFGA_STORE_ID=""))

    assert "OPENFGA_STORE_ID" in str(excinfo.value)


def test_openfga_store_id_present_passes() -> None:
    ensure_startup_config(_settings(**_VALID_OIDC_OVERRIDES, OPENFGA_STORE_ID="01ABCXYZ"))


def test_disable_auth_skips_openfga_validation() -> None:
    """`DISABLE_AUTH` skips OpenFGA validation too — RegistryService's
    `_openfga_client_for` bypasses OpenFGA entirely for that mode's
    "local"-issuer principal, so requiring a store id here would demand
    configuration nothing would ever use."""
    ensure_startup_config(_settings(DISABLE_AUTH="true", OPENFGA_STORE_ID=""))

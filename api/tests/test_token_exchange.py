from unittest.mock import patch

import pytest

from mismapi.auth.oidc import (
    JWT_ACCESS_TOKEN_TYPE,
    OIDCDiscoveryDocument,
    exchange_access_token_for_audience,
)
from mismapi.core.errors import APIError
from mismapi.core.settings import Settings


def _settings() -> Settings:
    settings = Settings()
    settings.oidc_client_id = "discovery-api"
    settings.oidc_client_secret = "secret"
    settings.oidc_token_exchange_scopes = ""
    return settings


def _discovery() -> OIDCDiscoveryDocument:
    return OIDCDiscoveryDocument(
        issuer="https://issuer.example.com/realms/r",
        authorization_endpoint="https://issuer.example.com/auth",
        token_endpoint="https://issuer.example.com/token",
        jwks_uri="https://issuer.example.com/jwks",
        end_session_endpoint="",
    )


class _FakeExchangeClient:
    def __init__(self, token_payload: dict[str, object]) -> None:
        self._token_payload = token_payload

    async def fetch_token(self, *args: object, **kwargs: object) -> dict[str, object]:
        return self._token_payload

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_exchange_access_token_for_audience_success() -> None:
    body: dict[str, object] = {
        "access_token": "helx-at",
        "issued_token_type": JWT_ACCESS_TOKEN_TYPE,
        "expires_in": 90,
    }

    with patch(
        "mismapi.auth.oidc._build_token_exchange_oauth_client",
        return_value=_FakeExchangeClient(body),
    ):
        result = await exchange_access_token_for_audience(
            _discovery(),
            _settings(),
            subject_access_token="user-at",
            audience="helx",
        )
    assert result.access_token == "helx-at"
    assert result.issued_token_type == JWT_ACCESS_TOKEN_TYPE
    assert result.expires_in == 90


@pytest.mark.asyncio
async def test_exchange_rejects_wrong_issued_token_type() -> None:
    body: dict[str, object] = {
        "access_token": "x",
        "issued_token_type": "urn:ietf:params:oauth:token-type:refresh_token",
    }

    with patch(
        "mismapi.auth.oidc._build_token_exchange_oauth_client",
        return_value=_FakeExchangeClient(body),
    ):
        with pytest.raises(APIError) as excinfo:
            await exchange_access_token_for_audience(
                _discovery(),
                _settings(),
                subject_access_token="user-at",
                audience="helx",
            )
    assert excinfo.value.code == "auth_token_exchange_issued_type_mismatch"

"""RFC 8693 token exchange (OIDCService.exchange_for_audience) behavior.

Exercises the real ``OIDCService`` against an in-process ``respx`` mock of the
IdP token endpoint, so the test covers the full authlib + httpx wiring rather
than a hand-rolled fake client.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from mismapi.auth.oidc import JWT_ACCESS_TOKEN_TYPE, OIDCDiscoveryDocument
from mismapi.auth.oidc_discovery import OIDCDiscoveryCache
from mismapi.auth.oidc_service import OIDCService
from mismapi.core.errors import APIError
from mismapi.core.settings import Settings

TOKEN_ENDPOINT = "https://issuer.example.com/token"


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
        token_endpoint=TOKEN_ENDPOINT,
        jwks_uri="https://issuer.example.com/jwks",
        end_session_endpoint="",
    )


def _build_service() -> OIDCService:
    settings = _settings()
    cache = OIDCDiscoveryCache(settings=settings)
    cache.seed(_discovery())
    return OIDCService(settings=settings, discovery=cache)


@pytest.mark.asyncio
@respx.mock
async def test_exchange_for_audience_success() -> None:
    route = respx.post(TOKEN_ENDPOINT).mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "helx-at",
                "issued_token_type": JWT_ACCESS_TOKEN_TYPE,
                "expires_in": 90,
                "token_type": "Bearer",
            },
        )
    )

    service = _build_service()
    try:
        result = await service.exchange_for_audience(
            subject_access_token="user-at",
            audience="helx",
        )
    finally:
        await service.aclose()

    assert result.access_token == "helx-at"
    assert result.issued_token_type == JWT_ACCESS_TOKEN_TYPE
    assert result.expires_in == 90

    assert route.called
    body = route.calls.last.request.content.decode()
    assert "subject_token=user-at" in body
    assert "audience=helx" in body


@pytest.mark.asyncio
@respx.mock
async def test_exchange_rejects_wrong_issued_token_type() -> None:
    respx.post(TOKEN_ENDPOINT).mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "x",
                "issued_token_type": "urn:ietf:params:oauth:token-type:refresh_token",
                "token_type": "Bearer",
            },
        )
    )

    service = _build_service()
    try:
        with pytest.raises(APIError) as excinfo:
            await service.exchange_for_audience(
                subject_access_token="user-at",
                audience="helx",
            )
    finally:
        await service.aclose()

    assert excinfo.value.code == "auth_token_exchange_issued_type_mismatch"


@pytest.mark.asyncio
@respx.mock
async def test_exchange_http_error_surfaces_as_api_error() -> None:
    respx.post(TOKEN_ENDPOINT).mock(
        return_value=httpx.Response(
            400,
            json={"error": "invalid_grant"},
        )
    )

    service = _build_service()
    try:
        with pytest.raises(APIError) as excinfo:
            await service.exchange_for_audience(
                subject_access_token="user-at",
                audience="helx",
            )
    finally:
        await service.aclose()

    assert excinfo.value.code == "auth_token_exchange_failed"

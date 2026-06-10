"""Callback success-path tests for post-login `return_to` resolution."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from mismapi.auth.oidc_types import TokenResponse
from mismapi.schemas.auth import OidcSessionRecord
from tests.conftest import build_test_app, minimal_oidc_settings


class _FakeSessionStore:
    def __init__(self) -> None:
        self.records: dict[str, OidcSessionRecord] = {}

    async def create(self, session_data: OidcSessionRecord) -> str:
        sid = f"sid-{len(self.records)}"
        self.records[sid] = session_data
        return sid


class _StubOIDCService:
    """Returns a canned token and a fixed return_to, bypassing the IdP."""

    def __init__(self, *, return_to_key: str | None, return_to_query: str | None) -> None:
        self._return_to = (return_to_key, return_to_query)

    async def pop_return_to(self, request: object) -> tuple[str | None, str | None]:
        return self._return_to

    async def authorize_access_token(self, request: object) -> TokenResponse:
        return TokenResponse(
            access_token="access",
            refresh_token="refresh",
            id_token="id-token",
            expires_in=3600,
        )


def _drive_callback(
    *, return_to_key: str | None, return_to_query: str | None, post_login: str = ""
) -> str:
    settings = minimal_oidc_settings(OIDC_POST_LOGIN_REDIRECT_URI=post_login)
    with build_test_app(settings) as app:
        with TestClient(app) as client:
            app.state.container.session_store = _FakeSessionStore()  # type: ignore[assignment]
            app.state.container.oidc_service = _StubOIDCService(  # type: ignore[assignment]
                return_to_key=return_to_key,
                return_to_query=return_to_query,
            )
            response = client.get(
                "/api/auth/callback",
                params={"code": "auth-code", "state": "state-value"},
                follow_redirects=False,
            )
    assert response.status_code == 302
    return response.headers["location"]


def test_return_to_key_with_query_round_trips_to_route() -> None:
    location = _drive_callback(return_to_key="search", return_to_query="q=foo")
    parsed = urlparse(location)
    assert parsed.path == "/search"
    assert parse_qs(parsed.query) == {"q": ["foo"]}


def test_unknown_return_to_key_falls_back_to_default() -> None:
    location = _drive_callback(return_to_key="admin", return_to_query=None)
    assert location == "/"


def test_no_return_to_uses_configured_post_login_uri() -> None:
    location = _drive_callback(
        return_to_key=None,
        return_to_query=None,
        post_login="https://app.example.com/home",
    )
    assert location == "https://app.example.com/home"


def test_no_return_to_and_no_config_falls_back_to_default() -> None:
    location = _drive_callback(return_to_key=None, return_to_query=None, post_login="")
    assert location == "/"

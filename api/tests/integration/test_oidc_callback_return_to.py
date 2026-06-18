"""End-to-end `return_to` round-trip through `request.session`.

The TestClient persists cookies across requests, so the SessionMiddleware
cookie written by /login is sent back into /callback. That's the contract:
return_to rides the session, no OAuth state involvement.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient
from starlette.responses import RedirectResponse

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
    """Bypasses the IdP: /login returns a redirect, /callback exchanges to a fake token."""

    async def authorize_redirect(self, request: object) -> RedirectResponse:
        return RedirectResponse(url="https://idp.example.com/authorize", status_code=302)

    async def authorize_access_token(self, request: object) -> TokenResponse:
        return TokenResponse(
            access_token="access",
            refresh_token="refresh",
            id_token="id-token",
            expires_in=3600,
        )


def _drive(
    *,
    login_query: dict[str, str] | None,
    post_login: str = "",
) -> str:
    settings = minimal_oidc_settings(OIDC_POST_LOGIN_REDIRECT_URI=post_login)
    with build_test_app(settings) as app:
        with TestClient(app) as client:
            app.state.container.session_store = _FakeSessionStore()  # type: ignore[assignment]
            app.state.container.oidc_service = _StubOIDCService()  # type: ignore[assignment]

            # /login: write return_to into the session cookie.
            login_response = client.get(
                "/api/auth/login",
                params=login_query or {},
                follow_redirects=False,
            )
            assert login_response.status_code == 302

            # /callback: TestClient sends the session cookie back automatically.
            callback_response = client.get(
                "/api/auth/callback",
                params={"code": "auth-code", "state": "state-value"},
                follow_redirects=False,
            )
    assert callback_response.status_code == 302
    return callback_response.headers["location"]


def test_return_to_key_round_trips_through_session() -> None:
    location = _drive(login_query={"return_to_key": "search", "return_to_query": "q=foo"})
    parsed = urlparse(location)
    assert parsed.path == "/search"
    assert parse_qs(parsed.query) == {"q": ["foo"]}


def test_unknown_key_falls_back_to_default() -> None:
    location = _drive(login_query={"return_to_key": "admin"})
    assert location == "/"


def test_no_return_to_uses_configured_post_login_uri() -> None:
    location = _drive(login_query=None, post_login="https://app.example.com/home")
    assert location == "https://app.example.com/home"


def test_no_return_to_and_no_config_falls_back_to_default() -> None:
    location = _drive(login_query=None, post_login="")
    assert location == "/"


def test_callback_without_prior_login_session_falls_back_to_default() -> None:
    # No /login was hit, so no session cookie. Callback should not crash.
    settings = minimal_oidc_settings(OIDC_POST_LOGIN_REDIRECT_URI="")
    with build_test_app(settings) as app:
        with TestClient(app) as client:
            app.state.container.session_store = _FakeSessionStore()  # type: ignore[assignment]
            app.state.container.oidc_service = _StubOIDCService()  # type: ignore[assignment]
            response = client.get(
                "/api/auth/callback",
                params={"code": "auth-code", "state": "state-value"},
                follow_redirects=False,
            )
    assert response.status_code == 302
    assert response.headers["location"] == "/"
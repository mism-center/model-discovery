"""Integration tests for ``GET /api/auth/me`` and ``POST /api/auth/logout``."""

from __future__ import annotations

import jwt
from fastapi.testclient import TestClient

from mismapi.schemas.auth import OidcSessionRecord
from tests.conftest import (
    build_test_app,
    default_principal,
    minimal_oidc_settings,
    override_principal,
)


class _FakeSessionStore:
    """In-memory ``SessionStore`` substitute keyed by caller-chosen ids."""

    def __init__(self) -> None:
        self.records: dict[str, OidcSessionRecord] = {}
        self.deleted: list[str] = []

    async def create(self, session_data: OidcSessionRecord) -> str:
        sid = f"sid-{len(self.records)}"
        self.records[sid] = session_data
        return sid

    async def get(self, session_id: str) -> OidcSessionRecord | None:
        return self.records.get(session_id)

    async def replace(self, session_id: str, session_data: OidcSessionRecord) -> None:
        self.records[session_id] = session_data

    async def delete(self, session_id: str) -> None:
        self.deleted.append(session_id)
        self.records.pop(session_id, None)

    def seed(self, session_id: str, record: OidcSessionRecord) -> None:
        self.records[session_id] = record


class _StubOIDCService:
    """Stub for ``OIDCService.build_end_session_url`` used by logout tests."""

    def __init__(self, end_session_url: str | None) -> None:
        self.end_session_url = end_session_url
        self.calls: list[str] = []

    async def build_end_session_url(self, *, id_token_hint: str) -> str | None:
        self.calls.append(id_token_hint)
        return self.end_session_url


def _make_id_token(claims: dict[str, object]) -> str:
    """Build a JWT-shaped string with the supplied claims.

    The endpoint decodes with ``verify_signature=False`` so the key/algorithm
    here are irrelevant — we just need a parseable token.
    """
    return jwt.encode(claims, "test-key-for-unverified-decode", algorithm="HS256")


def test_me_returns_principal_and_id_token_claims() -> None:
    settings = minimal_oidc_settings()
    with build_test_app(settings) as app:
        override_principal(app)
        with TestClient(app) as client:
            store = _FakeSessionStore()
            store.seed(
                "sid-active",
                OidcSessionRecord(
                    access_token="access",
                    refresh_token="refresh",
                    id_token=_make_id_token(
                        {
                            "email": "alice@example.org",
                            "name": "Alice Example",
                            "preferred_username": "alice",
                        }
                    ),
                    expires_at="0",
                ),
            )
            app.state.container.session_store = store  # type: ignore[assignment]
            client.cookies.set(settings.session_cookie_name, "sid-active")
            response = client.get("/api/auth/me")

    assert response.status_code == 200
    payload = response.json()
    principal = default_principal()
    assert payload["sub"] == principal.subject
    assert payload["iss"] == principal.issuer
    assert payload["scopes"] == []
    assert payload["email"] == "alice@example.org"
    assert payload["name"] == "Alice Example"
    assert payload["preferred_username"] == "alice"


def test_me_returns_null_claims_when_session_missing_id_token() -> None:
    settings = minimal_oidc_settings()
    with build_test_app(settings) as app:
        override_principal(app)
        with TestClient(app) as client:
            store = _FakeSessionStore()
            store.seed("sid-no-id", OidcSessionRecord(access_token="access"))
            app.state.container.session_store = store  # type: ignore[assignment]
            client.cookies.set(settings.session_cookie_name, "sid-no-id")
            response = client.get("/api/auth/me")

    assert response.status_code == 200
    payload = response.json()
    assert payload["email"] is None
    assert payload["name"] is None
    assert payload["preferred_username"] is None


def test_me_requires_authentication() -> None:
    with build_test_app(minimal_oidc_settings()) as app:
        with TestClient(app) as client:
            response = client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "auth_missing"


def test_logout_returns_end_session_url_when_idp_supports_it() -> None:
    settings = minimal_oidc_settings()
    with build_test_app(settings) as app:
        with TestClient(app) as client:
            store = _FakeSessionStore()
            store.seed(
                "sid-active",
                OidcSessionRecord(access_token="access", id_token="id-token-value"),
            )
            stub = _StubOIDCService(end_session_url="https://idp.example.com/end?id=1")
            app.state.container.session_store = store  # type: ignore[assignment]
            app.state.container.oidc_service = stub  # type: ignore[assignment]
            client.cookies.set(settings.session_cookie_name, "sid-active")
            response = client.post("/api/auth/logout")

    assert response.status_code == 200
    assert response.json() == {"end_session_url": "https://idp.example.com/end?id=1"}
    assert store.deleted == ["sid-active"]
    assert stub.calls == ["id-token-value"]
    set_cookie = response.headers.get("set-cookie", "")
    assert settings.session_cookie_name in set_cookie


def test_logout_returns_null_end_session_url_when_idp_does_not_support_it() -> None:
    settings = minimal_oidc_settings()
    with build_test_app(settings) as app:
        with TestClient(app) as client:
            store = _FakeSessionStore()
            store.seed(
                "sid-active",
                OidcSessionRecord(access_token="access", id_token="id-token-value"),
            )
            app.state.container.session_store = store  # type: ignore[assignment]
            app.state.container.oidc_service = _StubOIDCService(end_session_url=None)  # type: ignore[assignment]
            client.cookies.set(settings.session_cookie_name, "sid-active")
            response = client.post("/api/auth/logout")

    assert response.status_code == 200
    assert response.json() == {"end_session_url": None}
    assert store.deleted == ["sid-active"]


def test_logout_without_session_cookie_still_returns_json() -> None:
    settings = minimal_oidc_settings()
    with build_test_app(settings) as app:
        with TestClient(app) as client:
            store = _FakeSessionStore()
            app.state.container.session_store = store  # type: ignore[assignment]
            app.state.container.oidc_service = _StubOIDCService(end_session_url=None)  # type: ignore[assignment]
            response = client.post("/api/auth/logout")

    assert response.status_code == 200
    assert response.json() == {"end_session_url": None}
    assert store.deleted == []

from fastapi.testclient import TestClient

from mismapi.core.container import AppContainer
from tests.conftest import build_test_app, minimal_oidc_settings


def test_route_requires_bearer_token() -> None:
    with build_test_app(minimal_oidc_settings()) as app:
        with TestClient(app) as client:
            response = client.get("/api/auth/me")
            assert response.status_code == 401
            payload = response.json()
            assert payload["error"]["code"] == "auth_missing"


def test_route_unexpected_auth_error_returns_internal_server_error() -> None:
    class BrokenAuthValidator:
        async def validate_token(self, token: str) -> object:
            raise RuntimeError("unexpected validator failure")

    with build_test_app(minimal_oidc_settings()) as app:
        with TestClient(app, raise_server_exceptions=False) as client:
            container: AppContainer = app.state.container
            container.auth_validator = BrokenAuthValidator()  # type: ignore[assignment]
            response = client.get(
                "/api/auth/me",
                headers={"Authorization": "Bearer token-value"},
            )
            assert response.status_code == 500

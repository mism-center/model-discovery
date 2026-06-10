from fastapi.testclient import TestClient

from tests.conftest import build_test_app, minimal_oidc_settings


def test_callback_idp_error_redirects_to_login_with_params() -> None:
    settings = minimal_oidc_settings(OIDC_POST_LOGIN_REDIRECT_URI="")
    with build_test_app(settings) as app:
        with TestClient(app) as client:
            response = client.get(
                "/api/auth/callback",
                params={
                    "error": "access_denied",
                    "error_description": "not allowed by user",
                },
                follow_redirects=False,
            )

    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith("/")
    assert not location.startswith("/api/auth/login")
    assert "auth_error=access_denied" in location
    assert "auth_error_description" in location

from fastapi.testclient import TestClient

from mismapi.core.settings import Settings, clear_settings_cache
from mismapi.main import create_app


def test_callback_idp_error_redirects_to_login_with_params() -> None:
    clear_settings_cache()
    try:
        settings = Settings(OIDC_POST_LOGIN_REDIRECT_URI="")

        def _patched_get_settings() -> Settings:
            return settings

        import mismapi.main as main_mod

        prev = main_mod.get_settings
        main_mod.get_settings = _patched_get_settings  # type: ignore[method-assign]
        try:
            app = create_app()
            with TestClient(app) as client:
                response = client.get(
                    "/api/auth/callback",
                    params={
                        "error": "access_denied",
                        "error_description": "not allowed by user",
                    },
                    follow_redirects=False,
                )
        finally:
            main_mod.get_settings = prev  # type: ignore[method-assign]
    finally:
        clear_settings_cache()

    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith("/api/auth/login")
    assert "auth_error=access_denied" in location
    assert "auth_error_description" in location

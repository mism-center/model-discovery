from fastapi.testclient import TestClient

from tests.conftest import build_test_app, minimal_oidc_settings, override_principal


def test_execution_requires_helx_url_when_not_stub() -> None:
    settings = minimal_oidc_settings(
        OIDC_REQUIRED_SCOPES="openid",
        STUB_UPSTREAM_SERVICES="false",
        HELX_EXEC_PLATFORM_BASE_URL="",
    )
    with build_test_app(settings) as app:
        override_principal(app)

        with TestClient(app) as client:
            response = client.post("/api/v1/executions", json={})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "execution_exec_platform_unconfigured"


def test_execution_stub_happy_path() -> None:
    settings = minimal_oidc_settings(
        OIDC_REQUIRED_SCOPES="openid",
        STUB_UPSTREAM_SERVICES="true",
    )
    with build_test_app(settings) as app:
        override_principal(app)

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/executions",
                json={"model_id": "m-1", "parameters": {"k": "v"}},
            )

    assert response.status_code == 200
    data = response.json()
    assert data["state"] == "accepted"
    assert data["upstream_http_status"] == 202
    assert data["execution_id"] is not None
    assert data["poll_after_seconds"] == 5

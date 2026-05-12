from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mismapi.core.errors import APIError, register_exception_handlers
from tests.conftest import build_test_app, minimal_oidc_settings


def test_unhandled_exception_calls_logger_exception() -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/_boom")
    async def _boom() -> None:
        raise RuntimeError("boom")

    with patch("mismapi.core.errors.logger.exception") as log_exception:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/_boom")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "boom" in response.json()["error"]["detail"]
    assert log_exception.call_count == 1


def test_unhandled_exception_full_app_json_body() -> None:
    with build_test_app(minimal_oidc_settings()) as app:

        async def _boom() -> None:
            raise RuntimeError("boom")

        app.add_api_route("/_test_boom", _boom, methods=["GET"])
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/_test_boom")

    assert response.status_code == 500
    payload = response.json()
    assert payload["error"]["code"] == "internal_error"
    assert "boom" in payload["error"]["detail"]


def test_api_error_does_not_use_unhandled_logger() -> None:
    app = FastAPI()

    @app.get("/_conflict")
    async def _conflict() -> None:
        raise APIError(status_code=409, code="x", detail="nope")

    register_exception_handlers(app)
    with patch("mismapi.core.errors.logger.exception") as log_exception:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/_conflict")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "x"
    assert log_exception.call_count == 0

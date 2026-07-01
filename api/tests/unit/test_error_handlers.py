from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mismapi.core.errors import APIError, register_exception_handlers
from mismapi.schemas.common import ModelId
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


def test_request_validation_error_uses_error_envelope() -> None:
    app = FastAPI()

    @app.get("/_needs_query")
    async def _needs_query(q: str) -> dict[str, str]:
        return {"q": q}

    register_exception_handlers(app)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/_needs_query")

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "validation_error"
    assert payload["error"]["detail"] == "Request validation failed for field 'q'."


def test_model_id_pattern_validation_error_includes_field_name() -> None:
    app = FastAPI()

    @app.get("/_models/{model_id}")
    async def _read_model(model_id: ModelId) -> dict[str, str]:
        return {"id": model_id}

    register_exception_handlers(app)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/_models/sj8389f8932jf")

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "validation_error"
    assert payload["error"]["detail"] == "Request validation failed for field 'model_id'."

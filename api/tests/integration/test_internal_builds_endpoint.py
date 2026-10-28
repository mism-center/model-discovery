"""End-to-end tests for `POST /api/internal/builds` (exec → discovery callback).

Mounted outside the v1 auth chain like the tusd hooks: the execution API
posts without a Bearer token.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import create_autospec

from fastapi.testclient import TestClient
from mism_registry.enums import EnvBuildStatus

from mismapi.core.deps import _get_registry_service, _get_settings
from mismapi.core.errors import APIError
from mismapi.main import create_app
from mismapi.services.registry_service import RegistryService
from tests.conftest import minimal_oidc_settings
from tests.unit.test_models_endpoint import _make_model

# Sample body in the execution API's shape, including fields discovery ignores.
BODY: dict[str, Any] = {
    "resource_id": "m-1",
    "run_id": "98d9da1c66",
    "job": {"name": "envbuild-98d9da1c66", "status": "succeeded", "exit_code": None},
    "outcome": "verified",
    "image": {"ref": "docker.io/mismplatform/envbuild@sha256:8e05fd", "digest": "sha256:8e05fd"},
    "ladder_reached": "L3",
    "reason": "",
    "failure_class": None,
    "routes_to": "retry",
    "runtime": {"entrypoint": [], "mount": {"output_path": "/outputs"}, "env_vars": {}},
    "artifacts": {"dockerfile": "FROM x", "annotation_patch": None},
    "attempts": [{"attempt": 1, "action": {"type": "ADD_PKG", "arg": "arrow"}}],
    "verdict": {"entrypoint_used": "python run.py"},
}


def _client(service: RegistryService) -> TestClient:
    settings = minimal_oidc_settings()
    app = create_app(settings=settings)
    app.dependency_overrides[_get_settings] = lambda: settings
    app.dependency_overrides[_get_registry_service] = lambda: service
    return TestClient(app)


def test_callback_applies_result_without_auth() -> None:
    service = create_autospec(RegistryService, instance=True)
    service.apply_build_result.return_value = _make_model()
    response = _client(service).post("/api/internal/builds", json=BODY)

    assert response.status_code == 200
    result = service.apply_build_result.call_args.args[0]
    assert result.resource_id == "m-1"
    assert result.succeeded
    assert result.entry_command == "python run.py"


def test_callback_missing_outcome_is_400() -> None:
    service = create_autospec(RegistryService, instance=True)
    body = {k: v for k, v in BODY.items() if k != "outcome"}
    assert _client(service).post("/api/internal/builds", json=body).status_code == 400
    service.apply_build_result.assert_not_called()


def test_callback_unknown_model_is_404() -> None:
    service = create_autospec(RegistryService, instance=True)
    service.apply_build_result.side_effect = APIError(
        status_code=404, code="not_found", detail="nope"
    )
    assert _client(service).post("/api/internal/builds", json=BODY).status_code == 404


def test_env_build_status_enum_round_trip() -> None:
    # Guards the string the UI/exec read back.
    assert EnvBuildStatus.RUNNABLE.value == "runnable"

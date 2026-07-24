from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient
from mism_registry.enums import RunStatus
from mism_registry.run import Run

from mismapi.auth.base import AuthenticatedPrincipal, require_principal
from mismapi.clients.execution_client import ExecutionClient
from mismapi.core.deps import _get_execution_client, _get_registry_service
from mismapi.main import create_app
from mismapi.services.registry_service import RegistryService
from tests.conftest import minimal_oidc_settings


def _make_run(
    *,
    id: str = "run-1",
    model_id: str = "model-1",
    model_version: str = "0.1.0",
    input_resource_ids: list[str] | None = None,
) -> Run:
    return Run(
        id=id,
        model_id=model_id,
        model_version=model_version,
        status=RunStatus.REGISTERED,
        input_resource_ids=input_resource_ids or ["ds-1"],
        parameters={"condition": "both"},
        triggered_by="user-1",
        notes="test run",
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
    )


async def _allow_principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        subject="user-1",
        issuer="test",
        audience="mism-api",
        scopes=set(),
    )


def _make_app(service: RegistryService, execution_client: ExecutionClient) -> TestClient:
    app = create_app(settings=minimal_oidc_settings())
    app.dependency_overrides[require_principal] = _allow_principal
    app.dependency_overrides[_get_registry_service] = lambda: service
    app.dependency_overrides[_get_execution_client] = lambda: execution_client
    return TestClient(app)


# ── POST /models/{model_id}/runs/execute (batch) ───────────────


def test_execute_run_batch_success() -> None:
    run = _make_run()
    service = MagicMock(spec=RegistryService)
    service.create_run.return_value = run

    exec_client = AsyncMock(spec=ExecutionClient)
    exec_client.launch_batch.return_value = {"run_id": run.id, "status": "registered"}

    client = _make_app(service, exec_client)
    response = client.post(
        "/api/v1/models/model-1/runs",
        json={
            "input_resource_ids": ["ds-1"],
            "notes": "test run",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["id"] == "run-1"
    assert payload["model_id"] == "model-1"
    assert payload["status"] == "registered"
    assert payload["input_resource_ids"] == ["ds-1"]
    assert payload["execution"]["run_id"] == "run-1"

    service.create_run.assert_called_once()
    exec_client.launch_batch.assert_awaited_once_with("run-1")


def test_execute_run_forwards_entrypoint_and_arguments() -> None:
    """entrypoint_index + arguments in the body reach service.create_run,
    where they are validated against the model's declared entry point."""
    run = _make_run()
    service = MagicMock(spec=RegistryService)
    service.create_run.return_value = run

    exec_client = AsyncMock(spec=ExecutionClient)
    exec_client.launch_batch.return_value = {"run_id": run.id, "status": "registered"}

    client = _make_app(service, exec_client)
    response = client.post(
        "/api/v1/models/model-1/runs",
        json={
            "input_resource_ids": ["ds-1"],
            "entrypoint_index": 2,
            "arguments": {"experiment": "7b"},
        },
    )

    assert response.status_code == 201
    _, kwargs = service.create_run.call_args
    assert kwargs["entrypoint_index"] == 2
    assert kwargs["arguments"] == {"experiment": "7b"}


def test_execute_run_batch_default_mode() -> None:
    """When no mode specified, defaults to batch."""
    run = _make_run()
    service = MagicMock(spec=RegistryService)
    service.create_run.return_value = run

    exec_client = AsyncMock(spec=ExecutionClient)
    exec_client.launch_batch.return_value = {"run_id": run.id, "status": "registered"}

    client = _make_app(service, exec_client)
    response = client.post(
        "/api/v1/models/model-1/runs",
        json={},
    )

    assert response.status_code == 201
    exec_client.launch_batch.assert_awaited_once()
    exec_client.launch_interactive.assert_not_awaited()


# ── POST /models/{model_id}/runs/execute (interactive) ──────────


def test_execute_run_interactive_success() -> None:
    run = _make_run()
    service = MagicMock(spec=RegistryService)
    service.create_run.return_value = run

    exec_client = AsyncMock(spec=ExecutionClient)
    exec_client.launch_interactive.return_value = {
        "run_id": run.id,
        "sid": "session-abc",
        "url": "https://mism-exec.apps.renci.org/session/abc",
    }

    client = _make_app(service, exec_client)
    response = client.post(
        "/api/v1/models/model-1/runs",
        json={
            "input_resource_ids": ["ds-1"],
            "mode": "interactive",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["id"] == "run-1"
    assert payload["execution"]["sid"] == "session-abc"
    assert "url" in payload["execution"]

    exec_client.launch_interactive.assert_awaited_once_with("run-1")
    exec_client.launch_batch.assert_not_awaited()


# ── Error cases ─────────────────────────────────────────────────


def test_execute_run_invalid_mode_returns_422() -> None:
    service = MagicMock(spec=RegistryService)
    exec_client = AsyncMock(spec=ExecutionClient)

    client = _make_app(service, exec_client)
    response = client.post(
        "/api/v1/models/model-1/runs",
        json={"mode": "invalid"},
    )

    assert response.status_code == 422

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient
from mism_registry.enums import ExecutionType, ResourceStatus, ResourceType, RunStatus
from mism_registry.resource import Resource
from mism_registry.run import Run

from mismapi.auth.base import AuthenticatedPrincipal, require_principal
from mismapi.clients.execution_client import ExecutionClient
from mismapi.core.errors import APIError
from mismapi.dependencies.execution import get_execution_client
from mismapi.dependencies.registry import get_registry_service
from mismapi.main import create_app
from mismapi.services.registry_service import RegistryService


def _make_dataset(id: str = "d-1", name: str = "Dataset") -> Resource:
    return Resource(
        id=id,
        name=name,
        resource_type=ResourceType.DATASET,
        location_uri="s3://bucket/data.csv",
        description="Test dataset",
        version="1.0",
        status=ResourceStatus.ACTIVE,
        owner="user-1",
        format_tags=["csv"],
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
    )


def _make_run(
    *,
    id: str = "run-1",
    model_id: str = "m-1",
    status: RunStatus = RunStatus.COMPLETED,
    input_resource_ids: tuple[str, ...] = ("d-1",),
    output_resource_ids: tuple[str, ...] = (),
) -> Run:
    return Run(
        id=id,
        model_id=model_id,
        model_version="0.1.0",
        status=status,
        input_resource_ids=list(input_resource_ids),
        output_resource_ids=list(output_resource_ids),
        parameters={"condition": "wt"},
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
    app = create_app()
    app.dependency_overrides[require_principal] = _allow_principal
    app.dependency_overrides[get_registry_service] = lambda: service
    app.dependency_overrides[get_execution_client] = lambda: execution_client
    return TestClient(app)


# ── GET /runs/{run_id} ──────────────────────────────────────────


def test_get_run_calls_execution_then_dal() -> None:
    """Endpoint must call execution_client.get_status BEFORE service.get_run."""
    run = _make_run(status=RunStatus.COMPLETED)
    input_ds = _make_dataset(id="d-1", name="Input")

    call_order: list[str] = []

    service = MagicMock(spec=RegistryService)

    def _get_run(run_id: str) -> tuple[Run, list[Resource], list[Resource]]:
        call_order.append("dal")
        return run, [input_ds], []

    service.get_run.side_effect = _get_run

    exec_client = AsyncMock(spec=ExecutionClient)

    async def _get_status(run_id: str) -> dict:
        call_order.append("exec")
        return {"run_id": run_id, "status": "completed", "phase": "done"}

    exec_client.get_status.side_effect = _get_status

    client = _make_app(service, exec_client)
    response = client.get("/api/v1/runs/run-1")

    assert response.status_code == 200
    # Execution refresh must run BEFORE the DAL read.
    assert call_order == ["exec", "dal"]

    exec_client.get_status.assert_awaited_once_with("run-1")
    service.get_run.assert_called_once_with("run-1")


def test_get_run_returns_hydrated_payload() -> None:
    input_ds = _make_dataset(id="d-1", name="Input")
    output_ds = _make_dataset(id="d-2", name="Output")
    run = _make_run(
        id="run-1",
        status=RunStatus.COMPLETED,
        input_resource_ids=("d-1",),
        output_resource_ids=("d-2",),
    )

    service = MagicMock(spec=RegistryService)
    service.get_run.return_value = (run, [input_ds], [output_ds])

    exec_client = AsyncMock(spec=ExecutionClient)
    exec_client.get_status.return_value = {
        "run_id": "run-1",
        "status": "completed",
        "phase": "done",
    }

    client = _make_app(service, exec_client)
    response = client.get("/api/v1/runs/run-1")

    assert response.status_code == 200
    payload = response.json()

    assert payload["run"]["id"] == "run-1"
    assert payload["run"]["status"] == RunStatus.COMPLETED.value
    assert payload["run"]["input_resource_ids"] == ["d-1"]
    assert payload["run"]["output_resource_ids"] == ["d-2"]

    assert len(payload["input_resources"]) == 1
    assert payload["input_resources"][0]["id"] == "d-1"
    assert payload["input_resources"][0]["name"] == "Input"

    assert len(payload["output_resources"]) == 1
    assert payload["output_resources"][0]["id"] == "d-2"

    assert payload["execution_status"] == {
        "run_id": "run-1",
        "status": "completed",
        "phase": "done",
    }


def test_get_run_not_found_returns_404() -> None:
    service = MagicMock(spec=RegistryService)
    service.get_run.side_effect = APIError(
        status_code=404, code="not_found", detail="Run 'missing' not found"
    )

    exec_client = AsyncMock(spec=ExecutionClient)
    exec_client.get_status.return_value = {"run_id": "missing", "status": "unknown"}

    client = _make_app(service, exec_client)
    response = client.get("/api/v1/runs/missing")

    assert response.status_code == 404


def test_get_run_propagates_execution_error() -> None:
    """If the execution service is down, surface the error rather than silently
    falling through to the DAL — the whole point of this endpoint is freshness."""
    service = MagicMock(spec=RegistryService)

    exec_client = AsyncMock(spec=ExecutionClient)
    exec_client.get_status.side_effect = APIError(
        status_code=502,
        code="execution_status_failed",
        detail="Failed to reach execution service for run run-1.",
    )

    client = _make_app(service, exec_client)
    response = client.get("/api/v1/runs/run-1")

    assert response.status_code == 502
    # DAL must NOT be touched when the execution refresh fails.
    service.get_run.assert_not_called()


def test_get_run_handles_execution_timeout_504() -> None:
    service = MagicMock(spec=RegistryService)

    exec_client = AsyncMock(spec=ExecutionClient)
    exec_client.get_status.side_effect = APIError(
        status_code=504,
        code="execution_status_timeout",
        detail="Execution service status poll timed out for run run-1.",
    )

    client = _make_app(service, exec_client)
    response = client.get("/api/v1/runs/run-1")

    assert response.status_code == 504
    service.get_run.assert_not_called()


# ── refresh=false (skip execution round-trip) ───────────────────


def test_get_run_refresh_false_skips_execution() -> None:
    """refresh=false: DAL is read directly, Execution service is NOT called."""
    run = _make_run(status=RunStatus.RUNNING)
    service = MagicMock(spec=RegistryService)
    service.get_run.return_value = (run, [], [])

    exec_client = AsyncMock(spec=ExecutionClient)

    client = _make_app(service, exec_client)
    response = client.get("/api/v1/runs/run-1?refresh=false")

    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["id"] == "run-1"
    # No exec call was made → execution_status is empty.
    assert payload["execution_status"] == {}

    service.get_run.assert_called_once_with("run-1")
    exec_client.get_status.assert_not_called()


def test_get_run_refresh_false_still_404_on_missing_run() -> None:
    service = MagicMock(spec=RegistryService)
    service.get_run.side_effect = APIError(
        status_code=404, code="not_found", detail="Run 'missing' not found"
    )

    exec_client = AsyncMock(spec=ExecutionClient)

    client = _make_app(service, exec_client)
    response = client.get("/api/v1/runs/missing?refresh=false")

    assert response.status_code == 404
    exec_client.get_status.assert_not_called()


def test_get_run_refresh_default_is_true() -> None:
    """Omitting ?refresh defaults to true → execution IS called."""
    run = _make_run()
    service = MagicMock(spec=RegistryService)
    service.get_run.return_value = (run, [], [])

    exec_client = AsyncMock(spec=ExecutionClient)
    exec_client.get_status.return_value = {"run_id": "run-1", "status": "completed"}

    client = _make_app(service, exec_client)
    response = client.get("/api/v1/runs/run-1")

    assert response.status_code == 200
    exec_client.get_status.assert_awaited_once_with("run-1")


# ── DELETE /runs/{run_id} ───────────────────────────────────────


def test_cancel_run_calls_execution_then_dal() -> None:
    """Endpoint must call execution_client.cancel_run BEFORE service.get_run."""
    run = _make_run(status=RunStatus.CANCELLED)

    call_order: list[str] = []

    service = MagicMock(spec=RegistryService)

    def _get_run(run_id: str) -> tuple[Run, list[Resource], list[Resource]]:
        call_order.append("dal")
        return run, [], []

    service.get_run.side_effect = _get_run

    exec_client = AsyncMock(spec=ExecutionClient)

    async def _cancel(run_id: str) -> dict:
        call_order.append("exec")
        return {"run_id": run_id, "status": "cancelled"}

    exec_client.cancel_run.side_effect = _cancel

    client = _make_app(service, exec_client)
    response = client.delete("/api/v1/runs/run-1")

    assert response.status_code == 200
    # Cancel must be issued BEFORE we read the new state from the DAL.
    assert call_order == ["exec", "dal"]

    exec_client.cancel_run.assert_awaited_once_with("run-1")
    service.get_run.assert_called_once_with("run-1")


def test_cancel_run_returns_hydrated_payload() -> None:
    input_ds = _make_dataset(id="d-1", name="Input")
    run = _make_run(
        id="run-1",
        status=RunStatus.CANCELLED,
        input_resource_ids=("d-1",),
    )

    service = MagicMock(spec=RegistryService)
    service.get_run.return_value = (run, [input_ds], [])

    exec_client = AsyncMock(spec=ExecutionClient)
    exec_client.cancel_run.return_value = {"run_id": "run-1", "status": "cancelled"}

    client = _make_app(service, exec_client)
    response = client.delete("/api/v1/runs/run-1")

    assert response.status_code == 200
    payload = response.json()

    assert payload["run"]["id"] == "run-1"
    assert payload["run"]["status"] == RunStatus.CANCELLED.value
    assert len(payload["input_resources"]) == 1
    assert payload["input_resources"][0]["id"] == "d-1"
    assert payload["execution_status"] == {"run_id": "run-1", "status": "cancelled"}


def test_cancel_run_propagates_execution_error() -> None:
    """If exec service can't cancel, propagate — DAL must NOT be touched."""
    service = MagicMock(spec=RegistryService)

    exec_client = AsyncMock(spec=ExecutionClient)
    exec_client.cancel_run.side_effect = APIError(
        status_code=502,
        code="execution_cancel_failed",
        detail="Failed to reach execution service to cancel run run-1.",
    )

    client = _make_app(service, exec_client)
    response = client.delete("/api/v1/runs/run-1")

    assert response.status_code == 502
    service.get_run.assert_not_called()


def test_cancel_run_handles_execution_timeout_504() -> None:
    service = MagicMock(spec=RegistryService)

    exec_client = AsyncMock(spec=ExecutionClient)
    exec_client.cancel_run.side_effect = APIError(
        status_code=504,
        code="execution_cancel_timeout",
        detail="Execution service cancel timed out for run run-1.",
    )

    client = _make_app(service, exec_client)
    response = client.delete("/api/v1/runs/run-1")

    assert response.status_code == 504
    service.get_run.assert_not_called()


def test_cancel_run_not_found_returns_404() -> None:
    """Run vanished from DAL after exec cancel → 404 propagated from service."""
    service = MagicMock(spec=RegistryService)
    service.get_run.side_effect = APIError(
        status_code=404, code="not_found", detail="Run 'missing' not found"
    )

    exec_client = AsyncMock(spec=ExecutionClient)
    exec_client.cancel_run.return_value = {"run_id": "missing", "status": "cancelled"}

    client = _make_app(service, exec_client)
    response = client.delete("/api/v1/runs/missing")

    assert response.status_code == 404

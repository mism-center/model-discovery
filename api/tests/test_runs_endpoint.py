from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient
from mism_registry.enums import ResourceType, ResourceVersionStatus, RunStatus
from mism_registry.resource import Resource
from mism_registry.run import Run

from mismapi.clients.execution_client import ExecutionClient
from mismapi.core.deps import _get_execution_client, _get_registry_service
from mismapi.core.errors import APIError
from mismapi.main import create_app
from mismapi.services.registry_service import RegistryService
from tests.conftest import minimal_oidc_settings, override_anonymous, override_principal


def _make_dataset(id: str = "d-1", name: str = "Dataset") -> Resource:
    return Resource(
        id=id,
        name=name,
        resource_type=ResourceType.DATASET,
        location_uri="s3://bucket/data.csv",
        description="Test dataset",
        version="1.0",
        version_status=ResourceVersionStatus.ACTIVE,
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
    triggered_by: str = "user-1",
) -> Run:
    return Run(
        id=id,
        model_id=model_id,
        model_version="0.1.0",
        status=status,
        input_resource_ids=list(input_resource_ids),
        output_resource_ids=list(output_resource_ids),
        parameters={"condition": "wt"},
        triggered_by=triggered_by,
        notes="test run",
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
    )


def _make_app(
    service: RegistryService,
    execution_client: ExecutionClient,
    *,
    authenticated: bool = True,
) -> TestClient:
    app = create_app(settings=minimal_oidc_settings())
    if authenticated:
        override_principal(app)
    else:
        override_anonymous(app)
    app.dependency_overrides[_get_registry_service] = lambda: service
    app.dependency_overrides[_get_execution_client] = lambda: execution_client
    return TestClient(app)


# ── GET /runs/{run_id} ──────────────────────────────────────────


def test_get_run_calls_dal_then_execution_then_dal() -> None:
    """Endpoint must read the Run from the DAL FIRST (to authorize the caller
    against it), then call execution_client.get_status, then re-read the DAL
    so the response reflects whatever status Execution just wrote.

    This ordering is intentional: authorizing after the Execution round-trip
    would let an unauthorized caller trigger a live side effect (and observe
    its timing/error shape) on a run they don't own, before ever being
    rejected. See ``_authz.assert_run_owner`` and the docstring on
    ``get_run`` in ``runs.py``.
    """
    run = _make_run(status=RunStatus.COMPLETED)
    input_ds = _make_dataset(id="d-1", name="Input")

    call_order: list[str] = []

    service = MagicMock(spec=RegistryService)

    def _get_run(run_id: str) -> tuple[Run, list[Resource], list[Resource]]:
        call_order.append("dal")
        return run, [input_ds], []

    service.get_run.side_effect = _get_run

    exec_client = AsyncMock(spec=ExecutionClient)

    async def _get_status(run_id: str) -> dict[str, str]:
        call_order.append("exec")
        return {"run_id": run_id, "status": "completed", "phase": "done"}

    exec_client.get_status.side_effect = _get_status

    client = _make_app(service, exec_client)
    response = client.get("/api/v1/runs/run-1")

    assert response.status_code == 200
    # DAL read (authz) → execution refresh → DAL re-read.
    assert call_order == ["dal", "exec", "dal"]

    exec_client.get_status.assert_awaited_once_with("run-1")
    assert service.get_run.call_count == 2
    service.get_run.assert_called_with("run-1")


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
    # Missing run is caught on the authz read, before any Execution round-trip.
    exec_client.get_status.assert_not_called()


def test_get_run_propagates_execution_error() -> None:
    """If the execution service is down, surface the error rather than silently
    falling through to the DAL — the whole point of this endpoint is freshness."""
    run = _make_run(status=RunStatus.RUNNING)
    service = MagicMock(spec=RegistryService)
    service.get_run.return_value = (run, [], [])

    exec_client = AsyncMock(spec=ExecutionClient)
    exec_client.get_status.side_effect = APIError(
        status_code=502,
        code="execution_status_failed",
        detail="Failed to reach execution service for run run-1.",
    )

    client = _make_app(service, exec_client)
    response = client.get("/api/v1/runs/run-1")

    assert response.status_code == 502
    # The DAL read that happened was the authz read (once) — the endpoint
    # must NOT re-read the DAL when the execution refresh fails.
    service.get_run.assert_called_once_with("run-1")


def test_get_run_handles_execution_timeout_504() -> None:
    run = _make_run(status=RunStatus.RUNNING)
    service = MagicMock(spec=RegistryService)
    service.get_run.return_value = (run, [], [])

    exec_client = AsyncMock(spec=ExecutionClient)
    exec_client.get_status.side_effect = APIError(
        status_code=504,
        code="execution_status_timeout",
        detail="Execution service status poll timed out for run run-1.",
    )

    client = _make_app(service, exec_client)
    response = client.get("/api/v1/runs/run-1")

    assert response.status_code == 504
    service.get_run.assert_called_once_with("run-1")


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


def test_cancel_run_calls_dal_then_execution_then_dal() -> None:
    """Endpoint must read+authorize the Run from the DAL FIRST, only THEN call
    execution_client.cancel_run, then re-read the DAL for the final state.

    Authorizing before the cancel call is the security property under test:
    cancelling is destructive, so an unauthorized caller must never be able to
    trigger it — see ``_authz.assert_run_owner`` and the docstring on
    ``cancel_run`` in ``runs.py``.
    """
    run = _make_run(status=RunStatus.CANCELLED)

    call_order: list[str] = []

    service = MagicMock(spec=RegistryService)

    def _get_run(run_id: str) -> tuple[Run, list[Resource], list[Resource]]:
        call_order.append("dal")
        return run, [], []

    service.get_run.side_effect = _get_run

    exec_client = AsyncMock(spec=ExecutionClient)

    async def _cancel(run_id: str) -> dict[str, str]:
        call_order.append("exec")
        return {"run_id": run_id, "status": "cancelled"}

    exec_client.cancel_run.side_effect = _cancel

    client = _make_app(service, exec_client)
    response = client.delete("/api/v1/runs/run-1")

    assert response.status_code == 200
    # Authz DAL read → cancel → re-read the now-canceled state.
    assert call_order == ["dal", "exec", "dal"]

    exec_client.cancel_run.assert_awaited_once_with("run-1")
    assert service.get_run.call_count == 2
    service.get_run.assert_called_with("run-1")


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
    """If exec service can't cancel, propagate — the DAL must NOT be re-read
    for a post-cancel state that never happened (only the authz read runs)."""
    run = _make_run(status=RunStatus.RUNNING)
    service = MagicMock(spec=RegistryService)
    service.get_run.return_value = (run, [], [])

    exec_client = AsyncMock(spec=ExecutionClient)
    exec_client.cancel_run.side_effect = APIError(
        status_code=502,
        code="execution_cancel_failed",
        detail="Failed to reach execution service to cancel run run-1.",
    )

    client = _make_app(service, exec_client)
    response = client.delete("/api/v1/runs/run-1")

    assert response.status_code == 502
    service.get_run.assert_called_once_with("run-1")


def test_cancel_run_handles_execution_timeout_504() -> None:
    run = _make_run(status=RunStatus.RUNNING)
    service = MagicMock(spec=RegistryService)
    service.get_run.return_value = (run, [], [])

    exec_client = AsyncMock(spec=ExecutionClient)
    exec_client.cancel_run.side_effect = APIError(
        status_code=504,
        code="execution_cancel_timeout",
        detail="Execution service cancel timed out for run run-1.",
    )

    client = _make_app(service, exec_client)
    response = client.delete("/api/v1/runs/run-1")

    assert response.status_code == 504
    service.get_run.assert_called_once_with("run-1")


def test_cancel_run_not_found_returns_404() -> None:
    """Missing run → 404 on the authz read, before any Execution call."""
    service = MagicMock(spec=RegistryService)
    service.get_run.side_effect = APIError(
        status_code=404, code="not_found", detail="Run 'missing' not found"
    )

    exec_client = AsyncMock(spec=ExecutionClient)
    exec_client.cancel_run.return_value = {"run_id": "missing", "status": "cancelled"}

    client = _make_app(service, exec_client)
    response = client.delete("/api/v1/runs/missing")

    assert response.status_code == 404
    exec_client.cancel_run.assert_not_called()


# ── ownership authz ──────────────────────────────────────────────
# override_principal's default principal (tests/conftest.py) has
# subject "user-1"; these tests use runs triggered by other subjects (or no
# subject at all) to prove assert_run_owner rejects the mismatch with 404 —
# and, for the destructive DELETE path, that the mismatch is caught before
# the Execution call ever fires.


def test_get_run_someone_elses_run_returns_404() -> None:
    run = _make_run(id="run-1", triggered_by="user-2")
    service = MagicMock(spec=RegistryService)
    service.get_run.return_value = (run, [], [])

    exec_client = AsyncMock(spec=ExecutionClient)

    client = _make_app(service, exec_client)
    response = client.get("/api/v1/runs/run-1")

    assert response.status_code == 404
    # Rejected on the authz read — the Execution refresh must never fire.
    exec_client.get_status.assert_not_called()


def test_cancel_run_someone_elses_run_returns_404_and_never_calls_execution() -> None:
    """The destructive action must not fire before authorization succeeds."""
    run = _make_run(id="run-1", triggered_by="user-2")
    service = MagicMock(spec=RegistryService)
    service.get_run.return_value = (run, [], [])

    exec_client = AsyncMock(spec=ExecutionClient)

    client = _make_app(service, exec_client)
    response = client.delete("/api/v1/runs/run-1")

    assert response.status_code == 404
    exec_client.cancel_run.assert_not_called()


def test_get_run_empty_triggered_by_is_owned_by_nobody() -> None:
    """A run with an empty ``triggered_by`` (e.g. a historical row predating
    attribution) must be rejected even for an authenticated caller — it is
    not implicitly "unclaimed and thus fair game", it's owned by nobody."""
    run = _make_run(id="run-1", triggered_by="")
    service = MagicMock(spec=RegistryService)
    service.get_run.return_value = (run, [], [])

    exec_client = AsyncMock(spec=ExecutionClient)

    client = _make_app(service, exec_client)
    response = client.get("/api/v1/runs/run-1")

    assert response.status_code == 404
    exec_client.get_status.assert_not_called()


def test_cancel_run_empty_triggered_by_is_owned_by_nobody() -> None:
    run = _make_run(id="run-1", triggered_by="")
    service = MagicMock(spec=RegistryService)
    service.get_run.return_value = (run, [], [])

    exec_client = AsyncMock(spec=ExecutionClient)

    client = _make_app(service, exec_client)
    response = client.delete("/api/v1/runs/run-1")

    assert response.status_code == 404
    exec_client.cancel_run.assert_not_called()


# ── POST /runs/{run_id} (annotate) ──────────────────────────────


def test_annotate_resource_requires_auth() -> None:
    # This endpoint also depends on SettingsDep, which (unlike the
    # RegistryService/ExecutionClient overrides used elsewhere in this file)
    # resolves through the real app container — so it needs the lifespan to
    # have actually run, hence `with TestClient(...)` here rather than the
    # bare `_make_app(...)` used by the other tests in this file.
    service = MagicMock(spec=RegistryService)
    exec_client = AsyncMock(spec=ExecutionClient)

    app = create_app(settings=minimal_oidc_settings())
    override_anonymous(app)
    app.dependency_overrides[_get_registry_service] = lambda: service
    app.dependency_overrides[_get_execution_client] = lambda: exec_client

    with TestClient(app) as client:
        response = client.post("/api/v1/resources/run-1/annotate")

    assert response.status_code == 401
    exec_client.annotate.assert_not_called()


def test_annotate_resource_authenticated_triggers_annotation() -> None:
    service = MagicMock(spec=RegistryService)
    # The path param is a *resource* id (forwarded as `resource_id`), and the
    # caller must own it — `_make_dataset` is owned by "user-1", the subject
    # `override_principal` installs.
    service.get_model.return_value = _make_dataset(id="run-1")
    exec_client = AsyncMock(spec=ExecutionClient)
    exec_client.annotate.return_value = {"job_id": "job-1", "status": "queued"}

    app = create_app(settings=minimal_oidc_settings())
    override_principal(app)
    app.dependency_overrides[_get_registry_service] = lambda: service
    app.dependency_overrides[_get_execution_client] = lambda: exec_client

    with TestClient(app) as client:
        response = client.post("/api/v1/resources/run-1/annotate")

    assert response.status_code == 200
    payload = response.json()
    assert payload["resource_id"] == "run-1"
    assert payload["execution_status"] == {"job_id": "job-1", "status": "queued"}
    exec_client.annotate.assert_awaited_once()
    assert exec_client.annotate.call_args.kwargs["resource_id"] == "run-1"


def test_annotate_resource_someone_elses_resource_returns_404_and_never_annotates() -> None:
    """Annotation spends the deployment's LLM budget — visibility isn't enough."""
    resource = _make_dataset(id="res-1")
    resource.owner = "someone-else"

    service = MagicMock(spec=RegistryService)
    service.get_model.return_value = resource
    exec_client = AsyncMock(spec=ExecutionClient)

    app = create_app(settings=minimal_oidc_settings())
    override_principal(app)
    app.dependency_overrides[_get_registry_service] = lambda: service
    app.dependency_overrides[_get_execution_client] = lambda: exec_client

    with TestClient(app) as client:
        response = client.post("/api/v1/resources/res-1/annotate")

    assert response.status_code == 404
    exec_client.annotate.assert_not_awaited()


def test_annotate_resource_unowned_resource_is_owned_by_nobody() -> None:
    """An empty `owner` must not be treated as "owned by whoever asks"."""
    resource = _make_dataset(id="res-1")
    resource.owner = ""

    service = MagicMock(spec=RegistryService)
    service.get_model.return_value = resource
    exec_client = AsyncMock(spec=ExecutionClient)

    app = create_app(settings=minimal_oidc_settings())
    override_principal(app)
    app.dependency_overrides[_get_registry_service] = lambda: service
    app.dependency_overrides[_get_execution_client] = lambda: exec_client

    with TestClient(app) as client:
        response = client.post("/api/v1/resources/res-1/annotate")

    assert response.status_code == 404
    exec_client.annotate.assert_not_awaited()

from datetime import UTC, datetime
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from mism_registry.enums import ExecutionType, ResourceStatus, ResourceType, RunStatus
from mism_registry.resource import Resource
from mism_registry.run import Run
from mism_registry.run_detail import ModelRunDetail, ModelRunSummary

from mismapi.auth.base import AuthenticatedPrincipal, require_principal
from mismapi.core.deps import _get_registry_service
from mismapi.core.errors import APIError
from mismapi.main import create_app
from mismapi.services.registry_service import RegistryService
from tests.conftest import minimal_oidc_settings


def _make_model(id: str = "m-1", name: str = "Example Model") -> Resource:
    return Resource(
        id=id,
        name=name,
        resource_type=ResourceType.MODEL,
        location_uri="git+https://example.com/model.git",
        execution_type=ExecutionType.PYTHON,
        description="A test model",
        version="0.1.0",
        status=ResourceStatus.ACTIVE,
        owner="user-1",
        format_tags=["python"],
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
        execution_ref="ref",
    )


def _make_dataset(id: str = "d-1", name: str = "Input Dataset") -> Resource:
    return Resource(
        id=id,
        name=name,
        resource_type=ResourceType.DATASET,
        location_uri="s3://bucket/data.csv",
        description="Input dataset",
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


def _make_app_with_service(service: RegistryService) -> TestClient:
    app = create_app(settings=minimal_oidc_settings())
    app.dependency_overrides[require_principal] = _allow_principal
    app.dependency_overrides[_get_registry_service] = lambda: service
    return TestClient(app)


# ── GET /models/{model_id}/runs ─────────────────────────────────


def test_list_model_runs_empty() -> None:
    service = MagicMock(spec=RegistryService)
    service.get_model_run_details.return_value = ModelRunSummary(
        model=_make_model(),
        runs=[],
    )

    client = _make_app_with_service(service)
    response = client.get("/api/v1/models/m-1/runs")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 0
    assert payload["runs"] == []
    assert payload["model"]["id"] == "m-1"
    assert payload["model"]["resource_type"] == ResourceType.MODEL.value

    service.get_model_run_details.assert_called_once_with(model_id="m-1", status=None)


def test_list_model_runs_with_enriched_details() -> None:
    input_ds = _make_dataset(id="d-1", name="Input Dataset")
    output_ds = _make_dataset(id="d-2", name="Output Dataset")
    run = _make_run(
        id="run-1",
        input_resource_ids=("d-1",),
        output_resource_ids=("d-2",),
    )

    service = MagicMock(spec=RegistryService)
    service.get_model_run_details.return_value = ModelRunSummary(
        model=_make_model(),
        runs=[
            ModelRunDetail(
                run=run,
                input_resources=[input_ds],
                output_resources=[output_ds],
            )
        ],
    )

    client = _make_app_with_service(service)
    response = client.get("/api/v1/models/m-1/runs")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1

    run_detail = payload["runs"][0]
    assert run_detail["run"]["id"] == "run-1"
    assert run_detail["run"]["status"] == RunStatus.COMPLETED.value
    assert run_detail["run"]["parameters"] == {"condition": "wt"}
    assert run_detail["run"]["input_resource_ids"] == ["d-1"]
    assert run_detail["run"]["output_resource_ids"] == ["d-2"]

    assert len(run_detail["input_resources"]) == 1
    assert run_detail["input_resources"][0]["id"] == "d-1"
    assert run_detail["input_resources"][0]["name"] == "Input Dataset"

    assert len(run_detail["output_resources"]) == 1
    assert run_detail["output_resources"][0]["id"] == "d-2"


def test_list_model_runs_filters_by_status() -> None:
    run = _make_run(status=RunStatus.FAILED)
    service = MagicMock(spec=RegistryService)
    service.get_model_run_details.return_value = ModelRunSummary(
        model=_make_model(),
        runs=[
            ModelRunDetail(run=run, input_resources=[], output_resources=[]),
        ],
    )

    client = _make_app_with_service(service)
    response = client.get("/api/v1/models/m-1/runs?status=failed")

    assert response.status_code == 200
    assert response.json()["runs"][0]["run"]["status"] == RunStatus.FAILED.value

    service.get_model_run_details.assert_called_once_with(model_id="m-1", status=RunStatus.FAILED)


def test_list_model_runs_invalid_status_returns_422() -> None:
    service = MagicMock(spec=RegistryService)

    client = _make_app_with_service(service)
    response = client.get("/api/v1/models/m-1/runs?status=bogus")

    assert response.status_code == 422
    service.get_model_run_details.assert_not_called()


def test_list_model_runs_model_not_found_returns_404() -> None:
    service = MagicMock(spec=RegistryService)
    service.get_model_run_details.side_effect = APIError(
        status_code=404, code="not_found", detail="Resource 'missing' not found"
    )

    client = _make_app_with_service(service)
    response = client.get("/api/v1/models/missing/runs")

    assert response.status_code == 404


def test_list_model_runs_not_a_model_returns_400() -> None:
    service = MagicMock(spec=RegistryService)
    service.get_model_run_details.side_effect = APIError(
        status_code=400,
        code="validation_error",
        detail="Resource 'd-1' is a dataset, not a model or tool",
    )

    client = _make_app_with_service(service)
    response = client.get("/api/v1/models/d-1/runs")

    assert response.status_code == 400

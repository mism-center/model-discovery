from datetime import UTC, datetime
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from mism_registry import ModelRunDetail, ModelRunSummary
from mism_registry.enums import (
    ExecutionType,
    ResourceRegistrationStatus,
    ResourceType,
    ResourceVersionStatus,
    RunStatus,
)
from mism_registry.resource import Resource
from mism_registry.run import Run

from mismapi.core.deps import _get_registry_service
from mismapi.core.errors import APIError
from mismapi.main import create_app
from mismapi.services.registry_service import RegistryService
from tests.conftest import minimal_oidc_settings, override_anonymous, override_principal


def _make_model(id: str = "m-1", name: str = "Example Model", owner: str = "user-1") -> Resource:
    return Resource(
        id=id,
        name=name,
        resource_type=ResourceType.MODEL,
        location_uri="git+https://example.com/model.git",
        execution_type=ExecutionType.PYTHON,
        description="A test model",
        version="0.1.0",
        version_status=ResourceVersionStatus.ACTIVE,
        registration_status=ResourceRegistrationStatus.APPROVED,
        owner=owner,
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


def _make_app_with_service(service: RegistryService, *, authenticated: bool = True) -> TestClient:
    app = create_app(settings=minimal_oidc_settings())
    if authenticated:
        override_principal(app)
    else:
        override_anonymous(app)
    app.dependency_overrides[_get_registry_service] = lambda: service
    return TestClient(app)


# ── GET /models/{model_id}/runs ─────────────────────────────────


def test_list_model_runs_empty() -> None:
    service = MagicMock(spec=RegistryService)
    service.get_model.return_value = _make_model()
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

    service.get_model_run_details.assert_called_once_with(
        model_id="m-1", status=None, triggered_by="user-1"
    )


def test_list_model_runs_with_enriched_details() -> None:
    input_ds = _make_dataset(id="d-1", name="Input Dataset")
    output_ds = _make_dataset(id="d-2", name="Output Dataset")
    run = _make_run(
        id="run-1",
        input_resource_ids=("d-1",),
        output_resource_ids=("d-2",),
    )

    service = MagicMock(spec=RegistryService)
    service.get_model.return_value = _make_model()
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
    service.get_model.return_value = _make_model()
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

    service.get_model_run_details.assert_called_once_with(
        model_id="m-1", status=RunStatus.FAILED, triggered_by="user-1"
    )


def test_list_model_runs_invalid_status_returns_422() -> None:
    service = MagicMock(spec=RegistryService)
    service.get_model.return_value = _make_model()

    client = _make_app_with_service(service)
    response = client.get("/api/v1/models/m-1/runs?status=bogus")

    assert response.status_code == 422
    service.get_model_run_details.assert_not_called()


def test_list_model_runs_model_not_found_returns_404() -> None:
    service = MagicMock(spec=RegistryService)
    service.get_model.side_effect = APIError(
        status_code=404, code="not_found", detail="Resource 'missing' not found"
    )

    client = _make_app_with_service(service)
    response = client.get("/api/v1/models/missing/runs")

    assert response.status_code == 404
    service.get_model_run_details.assert_not_called()


def test_list_model_runs_not_a_model_returns_400() -> None:
    service = MagicMock(spec=RegistryService)
    service.get_model.side_effect = APIError(
        status_code=400,
        code="validation_error",
        detail="Resource 'd-1' is a dataset, not a model or tool",
    )

    client = _make_app_with_service(service)
    response = client.get("/api/v1/models/d-1/runs")

    assert response.status_code == 400
    service.get_model_run_details.assert_not_called()


# ── GET /models/{model_id}/runs — authz ─────────────────────────


def test_list_model_runs_requires_auth() -> None:
    service = MagicMock(spec=RegistryService)
    service.get_model.return_value = _make_model()

    client = _make_app_with_service(service, authenticated=False)
    response = client.get("/api/v1/models/m-1/runs")

    assert response.status_code == 401
    service.get_model_run_details.assert_not_called()


def test_list_model_runs_scopes_to_calling_user_only() -> None:
    """Regression test: this endpoint used to return every user's runs for the
    model. It must now return only the caller's, and the registry query itself
    (not a post-hoc filter) must be scoped via ``triggered_by``."""
    my_run = _make_run(id="run-mine", input_resource_ids=())
    service = MagicMock(spec=RegistryService)
    service.get_model.return_value = _make_model()
    # The fake only returns the caller's run — proving the endpoint passed
    # `triggered_by` into the query rather than relying on a filter here.
    service.get_model_run_details.return_value = ModelRunSummary(
        model=_make_model(),
        runs=[ModelRunDetail(run=my_run, input_resources=[], output_resources=[])],
    )

    client = _make_app_with_service(service)
    response = client.get("/api/v1/models/m-1/runs")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["runs"][0]["run"]["id"] == "run-mine"

    service.get_model_run_details.assert_called_once_with(
        model_id="m-1", status=None, triggered_by="user-1"
    )


def test_list_model_runs_excludes_other_users_runs_end_to_end() -> None:
    """Same regression as above, but through a real ``RegistryService`` backed
    by a fake ``Registry`` — proves the ``triggered_by`` filter is actually
    forwarded into the registry query rather than relying on a mock's canned
    ``get_model_run_details`` return_value."""
    from mism_registry import ResourceNotFoundError
    from mism_registry.protocol import Registry
    from sqlalchemy.orm import Session

    model = _make_model()
    mine = _make_run(id="run-mine", triggered_by="user-1")
    theirs = _make_run(id="run-theirs", triggered_by="user-2")
    all_runs = [mine, theirs]

    registry = MagicMock(spec=Registry)

    def _get_resource(rid: str) -> Resource:
        if rid == model.id:
            return model
        raise ResourceNotFoundError(f"Resource '{rid}' not found")

    def _get_model_run_details(
        model_id: str,
        *,
        status: RunStatus | None = None,
        triggered_by: str | None = None,
    ) -> ModelRunSummary:
        runs = [r for r in all_runs if r.model_id == model_id]
        if status is not None:
            runs = [r for r in runs if r.status == status]
        if triggered_by is not None:
            runs = [r for r in runs if r.triggered_by == triggered_by]
        return ModelRunSummary(
            model=model,
            runs=[ModelRunDetail(run=r, input_resources=[], output_resources=[]) for r in runs],
        )

    registry.get_resource.side_effect = _get_resource
    registry.get_model_run_details.side_effect = _get_model_run_details

    service = RegistryService(registry=registry, session=MagicMock(spec=Session))

    client = _make_app_with_service(service)
    response = client.get("/api/v1/models/m-1/runs")

    assert response.status_code == 200
    payload = response.json()
    ids = [item["run"]["id"] for item in payload["runs"]]
    assert ids == ["run-mine"]
    assert "run-theirs" not in ids

from datetime import UTC, datetime
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from mism_registry import ResourceNotFoundError
from mism_registry.enums import ExecutionType, ResourceType, ResourceVersionStatus, RunStatus
from mism_registry.protocol import Registry
from mism_registry.resource import Resource
from mism_registry.run import Run
from sqlalchemy.orm import Session

from mismapi.auth.base import AuthenticatedPrincipal, require_principal
from mismapi.core.deps import _get_registry_service
from mismapi.core.errors import APIError
from mismapi.main import create_app
from mismapi.services.registry_service import RegistryService
from tests.conftest import minimal_oidc_settings


def _make_model(id: str, name: str = "Example Model", owner: str = "user-1") -> Resource:
    return Resource(
        id=id,
        name=name,
        resource_type=ResourceType.MODEL,
        location_uri="git+https://example.com/model.git",
        execution_type=ExecutionType.PYTHON,
        description="A test model",
        version="0.1.0",
        version_status=ResourceVersionStatus.ACTIVE,
        owner=owner,
        format_tags=["python"],
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
        execution_ref="ref",
    )


def _make_dataset(id: str, name: str = "Dataset") -> Resource:
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
    id: str,
    model_id: str,
    triggered_by: str,
    status: RunStatus = RunStatus.COMPLETED,
    created_at: datetime,
    input_resource_ids: tuple[str, ...] = (),
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
        triggered_by=triggered_by,
        notes="test run",
        created_at=created_at,
    )


async def _allow_principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        subject="user-1",
        issuer="test",
        audience="mism-api",
        scopes=set(),
    )


async def _deny_principal() -> AuthenticatedPrincipal:
    # Mirror what the real require_principal raises for an anonymous caller
    # (no session cookie) — lets us assert the endpoint enforces auth without
    # needing Redis/OIDC infra.
    raise APIError(status_code=401, code="auth_missing", detail="Missing credentials.")


def _build_service(*, runs: list[Run], resources: list[Resource]) -> RegistryService:
    """Real RegistryService backed by a fake registry so hydration runs for real."""
    by_id = {r.id: r for r in resources}
    registry = MagicMock(spec=Registry)

    def _find_runs(
        *,
        model_id: str | None = None,
        input_resource_id: str | None = None,
        status: RunStatus | None = None,
    ) -> list[Run]:
        result = list(runs)
        if model_id is not None:
            result = [r for r in result if r.model_id == model_id]
        if status is not None:
            result = [r for r in result if r.status == status]
        return result

    def _get_resource(rid: str) -> Resource:
        try:
            return by_id[rid]
        except KeyError as exc:
            raise ResourceNotFoundError(f"Resource '{rid}' not found") from exc

    registry.find_runs.side_effect = _find_runs
    registry.get_resource.side_effect = _get_resource
    return RegistryService(registry=registry, session=MagicMock(spec=Session))


def _make_app(service: RegistryService, *, authenticated: bool = True) -> TestClient:
    app = create_app(settings=minimal_oidc_settings())
    app.dependency_overrides[require_principal] = (
        _allow_principal if authenticated else _deny_principal
    )
    app.dependency_overrides[_get_registry_service] = lambda: service
    return TestClient(app)


# ── GET /me/runs ─────────────────────────────────────────────────


def test_my_runs_returns_only_callers_runs_newest_first() -> None:
    model_a = _make_model("m-a", name="Model A")
    model_b = _make_model("m-b", name="Model B")
    ds = _make_dataset("d-1")

    # user-1 (caller) has two runs across two models; user-2 has one that must
    # never appear.
    mine_old = _make_run(
        id="run-old",
        model_id="m-a",
        triggered_by="user-1",
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
        input_resource_ids=("d-1",),
    )
    mine_new = _make_run(
        id="run-new",
        model_id="m-b",
        triggered_by="user-1",
        created_at=datetime(2025, 6, 1, tzinfo=UTC),
    )
    other = _make_run(
        id="run-other",
        model_id="m-a",
        triggered_by="user-2",
        created_at=datetime(2025, 12, 1, tzinfo=UTC),
    )

    service = _build_service(
        runs=[mine_old, other, mine_new],
        resources=[model_a, model_b, ds],
    )
    client = _make_app(service)

    response = client.get("/api/v1/me/runs")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    ids = [item["run"]["id"] for item in payload["runs"]]
    assert ids == ["run-new", "run-old"]  # newest-first, other user's run excluded

    # Each row carries its own model summary + hydrated inputs.
    first, second = payload["runs"]
    assert first["model"]["id"] == "m-b"
    assert first["run"]["triggered_by"] == "user-1"
    assert second["model"]["id"] == "m-a"
    assert second["input_resources"][0]["id"] == "d-1"


def test_my_runs_filters_by_status() -> None:
    model_a = _make_model("m-a")
    running = _make_run(
        id="run-running",
        model_id="m-a",
        triggered_by="user-1",
        status=RunStatus.RUNNING,
        created_at=datetime(2025, 2, 1, tzinfo=UTC),
    )
    completed = _make_run(
        id="run-completed",
        model_id="m-a",
        triggered_by="user-1",
        status=RunStatus.COMPLETED,
        created_at=datetime(2025, 3, 1, tzinfo=UTC),
    )

    service = _build_service(runs=[running, completed], resources=[model_a])
    client = _make_app(service)

    response = client.get("/api/v1/me/runs?status=running")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["runs"][0]["run"]["id"] == "run-running"
    assert payload["runs"][0]["run"]["status"] == RunStatus.RUNNING.value


def test_my_runs_skips_run_with_missing_model() -> None:
    model_a = _make_model("m-a")
    good = _make_run(
        id="run-good",
        model_id="m-a",
        triggered_by="user-1",
        created_at=datetime(2025, 4, 1, tzinfo=UTC),
    )
    orphan = _make_run(
        id="run-orphan",
        model_id="m-gone",
        triggered_by="user-1",
        created_at=datetime(2025, 5, 1, tzinfo=UTC),
    )

    service = _build_service(runs=[good, orphan], resources=[model_a])
    client = _make_app(service)

    response = client.get("/api/v1/me/runs")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["runs"][0]["run"]["id"] == "run-good"


def test_my_runs_requires_auth() -> None:
    service = _build_service(runs=[], resources=[])
    client = _make_app(service, authenticated=False)

    response = client.get("/api/v1/me/runs")

    assert response.status_code == 401


def test_auth_required_endpoint_documents_401_in_openapi() -> None:
    """Routes that depend on a principal auto-advertise their 401.

    The 401 isn't declared per-route — ``install_openapi_customizations`` injects
    it for any operation whose dependency tree includes ``require_principal``.
    This guards that behaviour so new authenticated endpoints stay documented.
    """
    app = create_app(settings=minimal_oidc_settings())
    schema = app.openapi()

    op = schema["paths"]["/api/v1/me/runs"]["get"]
    assert "401" in op["responses"]
    assert (
        op["responses"]["401"]["content"]["application/json"]["schema"]["$ref"]
        == "#/components/schemas/ErrorResponse"
    )
    assert "ErrorResponse" in schema["components"]["schemas"]

from datetime import UTC, datetime
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from mism_registry.enums import ResourceStatus, ResourceType
from mism_registry.resource import Resource

from mismapi.auth.base import AuthenticatedPrincipal, require_principal
from mismapi.core.deps import _get_registry_service
from mismapi.main import create_app
from mismapi.services.registry_service import RegistryService


def _make_dataset(
    *,
    id: str = "d-1",
    name: str = "Example Dataset",
    description: str = "A test dataset",
    owner: str = "user-1",
    format_tags: list[str] | None = None,
) -> Resource:
    return Resource(
        id=id,
        name=name,
        resource_type=ResourceType.DATASET,
        location_uri="s3://bucket/data.csv",
        description=description,
        version="1.0",
        status=ResourceStatus.ACTIVE,
        owner=owner,
        format_tags=format_tags or ["csv"],
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
    app = create_app()
    app.dependency_overrides[require_principal] = _allow_principal
    app.dependency_overrides[_get_registry_service] = lambda: service
    return TestClient(app)


# ── POST /datasets ───────────────────────────────────────────────


def test_create_dataset_success() -> None:
    service = MagicMock(spec=RegistryService)
    service.create_dataset.return_value = _make_dataset()

    client = _make_app_with_service(service)
    response = client.post(
        "/api/v1/datasets",
        json={
            "name": "Example Dataset",
            "location_uri": "s3://bucket/data.csv",
            "format_tags": ["csv"],
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["id"] == "d-1"
    assert payload["name"] == "Example Dataset"
    assert payload["resource_type"] == ResourceType.DATASET.value
    assert payload["format_tags"] == ["csv"]

    service.create_dataset.assert_called_once()


def test_create_dataset_minimal() -> None:
    service = MagicMock(spec=RegistryService)
    service.create_dataset.return_value = _make_dataset()

    client = _make_app_with_service(service)
    response = client.post(
        "/api/v1/datasets",
        json={
            "name": "Minimal",
            "location_uri": "s3://bucket/file",
        },
    )

    assert response.status_code == 201


def test_create_dataset_missing_name_returns_400() -> None:
    service = MagicMock(spec=RegistryService)
    client = _make_app_with_service(service)

    response = client.post(
        "/api/v1/datasets",
        json={"location_uri": "s3://bucket/file"},
    )

    assert response.status_code == 400


# ── PUT /datasets/{id} ──────────────────────────────────────────


def test_update_dataset_success() -> None:
    updated = _make_dataset(description="updated description")
    service = MagicMock(spec=RegistryService)
    service.update_dataset.return_value = updated

    client = _make_app_with_service(service)
    response = client.put(
        "/api/v1/datasets/d-1",
        json={"description": "updated description"},
    )

    assert response.status_code == 200
    assert response.json()["description"] == "updated description"

    service.update_dataset.assert_called_once()
    call_kwargs = service.update_dataset.call_args
    assert call_kwargs.kwargs["dataset_id"] == "d-1"
    assert call_kwargs.kwargs["description"] == "updated description"
    assert call_kwargs.kwargs["name"] is None


def test_update_dataset_empty_body() -> None:
    service = MagicMock(spec=RegistryService)
    service.update_dataset.return_value = _make_dataset()

    client = _make_app_with_service(service)
    response = client.put("/api/v1/datasets/d-1", json={})

    assert response.status_code == 200
    service.update_dataset.assert_called_once()


# ── GET /datasets ────────────────────────────────────────────────


def test_list_datasets_returns_results() -> None:
    service = MagicMock(spec=RegistryService)
    service.list_datasets.return_value = [
        _make_dataset(id="d-1", name="Dataset A"),
        _make_dataset(id="d-2", name="Dataset B"),
    ]

    client = _make_app_with_service(service)
    response = client.get("/api/v1/datasets")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert payload["results"][0]["id"] == "d-1"
    assert payload["results"][1]["id"] == "d-2"

    service.list_datasets.assert_called_once_with(
        name_contains=None,
        owner=None,
        tags=None,
        organisms=None,
        scales=None,
    )


def test_list_datasets_empty() -> None:
    service = MagicMock(spec=RegistryService)
    service.list_datasets.return_value = []

    client = _make_app_with_service(service)
    response = client.get("/api/v1/datasets")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 0
    assert payload["results"] == []


def test_list_datasets_passes_filters() -> None:
    service = MagicMock(spec=RegistryService)
    service.list_datasets.return_value = [_make_dataset()]

    client = _make_app_with_service(service)
    response = client.get("/api/v1/datasets?name=climate&owner=bob&tags=csv&tags=public")

    assert response.status_code == 200

    filter_kwargs = dict(
        name_contains="climate",
        owner="bob",
        tags=["csv", "public"],
        organisms=None,
        scales=None,
    )
    service.list_datasets.assert_called_once_with(**filter_kwargs)


def test_list_datasets_pagination() -> None:
    resources = [_make_dataset(id=f"d-{i}", name=f"Dataset {i}") for i in range(5)]

    service = MagicMock(spec=RegistryService)
    service.list_datasets.return_value = resources

    client = _make_app_with_service(service)
    response = client.get("/api/v1/datasets?limit=2&offset=1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 5
    assert len(payload["results"]) == 2
    assert payload["results"][0]["id"] == "d-1"
    assert payload["results"][1]["id"] == "d-2"

    service.list_datasets.assert_called_once_with(
        name_contains=None,
        owner=None,
        tags=None,
        organisms=None,
        scales=None,
    )


def test_list_datasets_response_shape() -> None:
    service = MagicMock(spec=RegistryService)
    service.list_datasets.return_value = [_make_dataset()]

    client = _make_app_with_service(service)
    response = client.get("/api/v1/datasets")

    item = response.json()["results"][0]
    assert item["id"] == "d-1"
    assert item["name"] == "Example Dataset"
    assert item["resource_type"] == ResourceType.DATASET.value
    assert item["location_uri"] == "s3://bucket/data.csv"
    assert item["version"] == "1.0"
    assert item["status"] == ResourceStatus.ACTIVE.value
    assert item["owner"] == "user-1"
    assert item["description"] == "A test dataset"
    assert "created_at" in item

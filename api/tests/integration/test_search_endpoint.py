from datetime import UTC, datetime
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from mism_registry.enums import ExecutionType, ResourceStatus, ResourceType
from mism_registry.resource import Resource

from mismapi.auth.base import AuthenticatedPrincipal, require_principal
from mismapi.core.deps import get_registry_service
from mismapi.main import create_app
from mismapi.services.registry_service import RegistryService


def _make_resource(
    *,
    id: str = "r-1",
    name: str = "Example Model",
    description: str = "A test model",
    owner: str = "user-1",
) -> Resource:
    return Resource(
        id=id,
        name=name,
        resource_type=ResourceType.MODEL,
        location_uri="https://example.com/model",
        execution_type=ExecutionType.DOCKER,
        description=description,
        version="1.0",
        status=ResourceStatus.ACTIVE,
        owner=owner,
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
    app.dependency_overrides[get_registry_service] = lambda: service
    return TestClient(app)


def test_list_models_returns_results() -> None:
    service = MagicMock(spec=RegistryService)
    service.list_models.return_value = [
        _make_resource(id="r-1", name="Model A"),
        _make_resource(id="r-2", name="Model B"),
    ]

    client = _make_app_with_service(service)
    response = client.get("/api/v1/models")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert payload["results"][0]["id"] == "r-1"
    assert payload["results"][0]["name"] == "Model A"
    assert payload["results"][1]["id"] == "r-2"

    service.list_models.assert_called_once_with(
        name_contains=None,
        owner=None,
        tags=None,
        organisms=None,
        scales=None,
    )


def test_list_models_empty() -> None:
    service = MagicMock(spec=RegistryService)
    service.list_models.return_value = []

    client = _make_app_with_service(service)
    response = client.get("/api/v1/models")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 0
    assert payload["results"] == []


def test_list_models_passes_filters() -> None:
    service = MagicMock(spec=RegistryService)
    service.list_models.return_value = [_make_resource()]

    client = _make_app_with_service(service)
    response = client.get("/api/v1/models?name=hydro&owner=alice&tags=csv&tags=public")

    assert response.status_code == 200

    filter_kwargs = dict(
        name_contains="hydro",
        owner="alice",
        tags=["csv", "public"],
        organisms=None,
        scales=None,
    )
    service.list_models.assert_called_once_with(**filter_kwargs)


def test_list_models_pagination() -> None:
    resources = [_make_resource(id=f"r-{i}", name=f"Model {i}") for i in range(5)]

    service = MagicMock(spec=RegistryService)
    service.list_models.return_value = resources

    client = _make_app_with_service(service)
    response = client.get("/api/v1/models?limit=2&offset=1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 5
    assert len(payload["results"]) == 2
    assert payload["results"][0]["id"] == "r-1"
    assert payload["results"][1]["id"] == "r-2"

    service.list_models.assert_called_once_with(
        name_contains=None,
        owner=None,
        tags=None,
        organisms=None,
        scales=None,
    )


def test_list_models_response_shape() -> None:
    service = MagicMock(spec=RegistryService)
    service.list_models.return_value = [_make_resource()]

    client = _make_app_with_service(service)
    response = client.get("/api/v1/models")

    item = response.json()["results"][0]
    assert item["id"] == "r-1"
    assert item["name"] == "Example Model"
    assert item["resource_type"] == ResourceType.MODEL.value
    assert item["location_uri"] == "https://example.com/model"
    assert item["execution_type"] == ExecutionType.DOCKER.value
    assert item["version"] == "1.0"
    assert item["status"] == ResourceStatus.ACTIVE.value
    assert item["owner"] == "user-1"
    assert item["description"] == "A test model"
    assert "created_at" in item

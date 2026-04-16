from datetime import UTC, datetime
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from mism_registry.enums import ExecutionType, ResourceStatus, ResourceType
from mism_registry.resource import Resource

from mismapi.auth.base import AuthenticatedPrincipal, require_principal
from mismapi.dependencies.registry import get_registry_service
from mismapi.main import create_app
from mismapi.services.registry_service import RegistryService


def _make_model(
    *,
    id: str = "m-1",
    name: str = "Example Model",
    description: str = "A test model",
    owner: str = "user-1",
    execution_type: ExecutionType = ExecutionType.PYTHON,
    execution_ref: str = "",
    version: str = "0.1.0",
) -> Resource:
    return Resource(
        id=id,
        name=name,
        resource_type=ResourceType.MODEL,
        location_uri="git+https://example.com/model.git",
        execution_type=execution_type,
        execution_ref=execution_ref,
        description=description,
        version=version,
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


# ── POST /models ─────────────────────────────────────────────────


def test_create_model_success() -> None:
    service = MagicMock(spec=RegistryService)
    service.create_model.return_value = _make_model()

    client = _make_app_with_service(service)
    response = client.post(
        "/api/v1/models",
        json={
            "name": "Example Model",
            "location_uri": "git+https://example.com/model.git",
            "execution_type": "python",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["id"] == "m-1"
    assert payload["name"] == "Example Model"
    assert payload["resource_type"] == ResourceType.MODEL.value
    assert payload["execution_type"] == "python"

    service.create_model.assert_called_once()


def test_create_model_missing_name_returns_422() -> None:
    service = MagicMock(spec=RegistryService)
    client = _make_app_with_service(service)

    response = client.post(
        "/api/v1/models",
        json={
            "location_uri": "git+https://example.com/model.git",
            "execution_type": "python",
        },
    )

    assert response.status_code == 422
    service.create_model.assert_not_called()


def test_create_model_missing_execution_type_returns_422() -> None:
    service = MagicMock(spec=RegistryService)
    client = _make_app_with_service(service)

    response = client.post(
        "/api/v1/models",
        json={
            "name": "Example Model",
            "location_uri": "git+https://example.com/model.git",
        },
    )

    assert response.status_code == 422
    service.create_model.assert_not_called()


def test_create_model_invalid_execution_type_returns_422() -> None:
    service = MagicMock(spec=RegistryService)
    client = _make_app_with_service(service)

    response = client.post(
        "/api/v1/models",
        json={
            "name": "Example Model",
            "location_uri": "git+https://example.com/model.git",
            "execution_type": "bogus",
        },
    )

    assert response.status_code == 422
    service.create_model.assert_not_called()


# ── POST /models — execution_ref wiring ─────────────────────────


def test_create_model_forwards_execution_ref() -> None:
    service = MagicMock(spec=RegistryService)
    service.create_model.return_value = _make_model(execution_ref="docker://foo:1")

    client = _make_app_with_service(service)
    response = client.post(
        "/api/v1/models",
        json={
            "name": "Example Model",
            "location_uri": "docker://foo:1",
            "execution_type": "docker",
            "execution_ref": "docker://foo:1",
        },
    )

    assert response.status_code == 201

    service.create_model.assert_called_once()
    call_kwargs = service.create_model.call_args.kwargs
    assert call_kwargs["execution_ref"] == "docker://foo:1"


def test_create_model_response_includes_execution_ref() -> None:
    service = MagicMock(spec=RegistryService)
    service.create_model.return_value = _make_model(execution_ref="docker://foo:1")

    client = _make_app_with_service(service)
    response = client.post(
        "/api/v1/models",
        json={
            "name": "Example Model",
            "location_uri": "docker://foo:1",
            "execution_type": "docker",
            "execution_ref": "docker://foo:1",
        },
    )

    assert response.status_code == 201
    assert response.json()["execution_ref"] == "docker://foo:1"


def test_create_model_without_execution_ref_defaults_to_empty() -> None:
    """When client omits execution_ref, the service should be called with empty string."""
    service = MagicMock(spec=RegistryService)
    service.create_model.return_value = _make_model()

    client = _make_app_with_service(service)
    response = client.post(
        "/api/v1/models",
        json={
            "name": "Example Model",
            "location_uri": "git+https://example.com/model.git",
            "execution_type": "python",
        },
    )

    assert response.status_code == 201

    service.create_model.assert_called_once()
    call_kwargs = service.create_model.call_args.kwargs
    assert call_kwargs["execution_ref"] == ""


def test_create_model_null_execution_ref_defaults_to_empty() -> None:
    """When client sends execution_ref=null, service should be called with empty string."""
    service = MagicMock(spec=RegistryService)
    service.create_model.return_value = _make_model()

    client = _make_app_with_service(service)
    response = client.post(
        "/api/v1/models",
        json={
            "name": "Example Model",
            "location_uri": "git+https://example.com/model.git",
            "execution_type": "python",
            "execution_ref": None,
        },
    )

    assert response.status_code == 201

    service.create_model.assert_called_once()
    call_kwargs = service.create_model.call_args.kwargs
    assert call_kwargs["execution_ref"] == ""


# ── PUT /models/{id} ─────────────────────────────────────────────


def test_update_model_success() -> None:
    updated = _make_model(description="updated description")
    service = MagicMock(spec=RegistryService)
    service.update_model.return_value = updated

    client = _make_app_with_service(service)
    response = client.put(
        "/api/v1/models/m-1",
        json={"description": "updated description"},
    )

    assert response.status_code == 200
    # RegisterModelResponse doesn't include description — assert on the service call instead.
    assert response.json()["id"] == "m-1"

    service.update_model.assert_called_once()
    call_kwargs = service.update_model.call_args.kwargs
    assert call_kwargs["model_id"] == "m-1"
    assert call_kwargs["description"] == "updated description"
    assert call_kwargs["name"] is None


def test_update_model_empty_body() -> None:
    service = MagicMock(spec=RegistryService)
    service.update_model.return_value = _make_model()

    client = _make_app_with_service(service)
    response = client.put("/api/v1/models/m-1", json={})

    assert response.status_code == 200
    service.update_model.assert_called_once()


def test_update_model_forwards_execution_ref() -> None:
    service = MagicMock(spec=RegistryService)
    service.update_model.return_value = _make_model(execution_ref="docker://foo:2")

    client = _make_app_with_service(service)
    response = client.put(
        "/api/v1/models/m-1",
        json={"execution_ref": "docker://foo:2"},
    )

    assert response.status_code == 200

    service.update_model.assert_called_once()
    call_kwargs = service.update_model.call_args.kwargs
    assert call_kwargs["model_id"] == "m-1"
    assert call_kwargs["execution_ref"] == "docker://foo:2"


def test_update_model_response_includes_execution_ref() -> None:
    service = MagicMock(spec=RegistryService)
    service.update_model.return_value = _make_model(execution_ref="docker://foo:2")

    client = _make_app_with_service(service)
    response = client.put(
        "/api/v1/models/m-1",
        json={"execution_ref": "docker://foo:2"},
    )

    assert response.status_code == 200
    assert response.json()["execution_ref"] == "docker://foo:2"


def test_update_model_without_execution_ref_leaves_it_untouched() -> None:
    """PUT without execution_ref key: service is called with execution_ref=None (sentinel)."""
    service = MagicMock(spec=RegistryService)
    service.update_model.return_value = _make_model()

    client = _make_app_with_service(service)
    response = client.put(
        "/api/v1/models/m-1",
        json={"description": "new desc"},
    )

    assert response.status_code == 200

    service.update_model.assert_called_once()
    call_kwargs = service.update_model.call_args.kwargs
    assert call_kwargs["execution_ref"] is None

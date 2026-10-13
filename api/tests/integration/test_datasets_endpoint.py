from datetime import UTC, datetime
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from mism_registry.enums import ResourceType, ResourceVersionStatus
from mism_registry.resource import Resource

from mismapi.core.deps import _get_registry_service
from mismapi.main import create_app
from mismapi.services.registry_service import RegistryService
from tests.conftest import default_principal, override_principal


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
        location_uri="irods:///datasets/d-1",
        description=description,
        version="1.0",
        version_status=ResourceVersionStatus.ACTIVE,
        owner=owner,
        format_tags=format_tags or ["csv"],
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
    )


def _make_app_with_service(service: RegistryService) -> TestClient:
    app = create_app()
    # `override_principal` registers the fixed "user-1" principal for both
    # `require_principal` and `optional_principal` — `list_datasets` uses
    # `OptionalPrincipalDep` for its visibility filter (MISM-291 Phase A), so
    # overriding only `require_principal` would leave the real
    # `optional_principal` running outside a live request context.
    app.dependency_overrides[_get_registry_service] = lambda: service
    override_principal(app)
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
            "location_uri": "irods:///datasets/d-1",
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
            "location_uri": "irods:///datasets/d-1",
        },
    )

    assert response.status_code == 201


def test_create_dataset_missing_name_returns_400() -> None:
    service = MagicMock(spec=RegistryService)
    client = _make_app_with_service(service)

    response = client.post(
        "/api/v1/datasets",
        json={"location_uri": "irods:///datasets/d-1"},
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
        principal=default_principal(),
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
        principal=default_principal(),
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
        principal=default_principal(),
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
    assert item["location_uri"] == "irods:///datasets/d-1"
    assert item["version"] == "1.0"
    assert item["status"] == ResourceVersionStatus.ACTIVE.value
    assert item["owner"] == "user-1"
    assert item["description"] == "A test dataset"
    assert "created_at" in item


# ── New Resource fields ───────────────────────────────────────────


def test_create_dataset_forwards_attribution_fields() -> None:
    """POST /datasets passes authors, org, publications, funding to service."""
    service = MagicMock(spec=RegistryService)
    service.create_dataset.return_value = _make_dataset()

    client = _make_app_with_service(service)
    response = client.post(
        "/api/v1/datasets",
        json={
            "name": "Attr Dataset",
            "location_uri": "irods:///datasets/attr",
            "authors": [{"name": "Bob", "orcid": "", "affiliation": "UNC", "role": "curator"}],
            "organization": "UNC",
            "contact_email": "bob@unc.edu",
            "publications": [{"title": "Data Paper", "doi": "10.2/x", "url": "", "citation": ""}],
            "funding": ["NIH P41"],
        },
    )

    assert response.status_code == 201
    kwargs = service.create_dataset.call_args.kwargs
    assert kwargs["organization"] == "UNC"
    assert kwargs["contact_email"] == "bob@unc.edu"
    assert kwargs["funding"] == ["NIH P41"]
    assert kwargs["authors"][0].name == "Bob"
    assert kwargs["publications"][0].title == "Data Paper"


def test_create_dataset_forwards_scientific_fields() -> None:
    """POST /datasets passes model_scales, organisms, domains, date_published to service."""
    service = MagicMock(spec=RegistryService)
    service.create_dataset.return_value = _make_dataset()

    client = _make_app_with_service(service)
    response = client.post(
        "/api/v1/datasets",
        json={
            "name": "Sci Dataset",
            "location_uri": "irods:///datasets/sci",
            "model_scales": ["population"],
            "organisms": ["rat"],
            "domains": ["neuroscience"],
            "date_published": "2023-05-10",
        },
    )

    assert response.status_code == 201
    kwargs = service.create_dataset.call_args.kwargs
    assert kwargs["model_scales"] == ["population"]
    assert kwargs["organisms"] == ["rat"]
    assert kwargs["domains"] == ["neuroscience"]
    assert str(kwargs["date_published"]) == "2023-05-10"


def test_create_dataset_forwards_integrity_fields() -> None:
    """POST /datasets passes digest_sha256, size_bytes, external_ids, license to service."""
    service = MagicMock(spec=RegistryService)
    service.create_dataset.return_value = _make_dataset()

    client = _make_app_with_service(service)
    response = client.post(
        "/api/v1/datasets",
        json={
            "name": "Integrity Dataset",
            "location_uri": "irods:///datasets/ig",
            "digest_sha256": "xyz789",
            "size_bytes": 2048,
            "external_ids": {"zenodo": "654321"},
            "license": "CC-BY-4.0",
        },
    )

    assert response.status_code == 201
    kwargs = service.create_dataset.call_args.kwargs
    assert kwargs["digest_sha256"] == "xyz789"
    assert kwargs["size_bytes"] == 2048
    assert kwargs["external_ids"] == {"zenodo": "654321"}
    assert kwargs["license"] == "CC-BY-4.0"


def test_create_dataset_response_includes_new_fields() -> None:
    """POST /datasets response contains updated_at, metadata, and all new fields."""
    service = MagicMock(spec=RegistryService)
    service.create_dataset.return_value = _make_dataset()

    client = _make_app_with_service(service)
    response = client.post(
        "/api/v1/datasets",
        json={"name": "New Fields Dataset", "location_uri": "irods:///datasets/nf"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert "updated_at" in payload
    assert "metadata" in payload
    assert "authors" in payload
    assert "organization" in payload
    assert "contact_email" in payload
    assert "publications" in payload
    assert "funding" in payload
    assert "model_scales" in payload
    assert "organisms" in payload
    assert "domains" in payload
    assert "date_published" in payload
    assert "digest_sha256" in payload
    assert "size_bytes" in payload
    assert "external_ids" in payload
    assert "license" in payload


def test_update_dataset_forwards_new_fields() -> None:
    """PUT /datasets/{id} passes all new fields to service when present."""
    service = MagicMock(spec=RegistryService)
    service.update_dataset.return_value = _make_dataset()

    client = _make_app_with_service(service)
    response = client.put(
        "/api/v1/datasets/d-1",
        json={
            "organization": "New Org",
            "contact_email": "new@org.com",
            "organisms": ["mouse"],
            "license": "GPL-3.0",
            "size_bytes": 1024,
            "funding": ["NSF"],
        },
    )

    assert response.status_code == 200
    kwargs = service.update_dataset.call_args.kwargs
    assert kwargs["organization"] == "New Org"
    assert kwargs["contact_email"] == "new@org.com"
    assert kwargs["organisms"] == ["mouse"]
    assert kwargs["license"] == "GPL-3.0"
    assert kwargs["size_bytes"] == 1024
    assert kwargs["funding"] == ["NSF"]


def test_update_dataset_omitted_new_fields_are_none() -> None:
    """PUT /datasets/{id} omitting new fields passes None (no-op sentinel) to service."""
    service = MagicMock(spec=RegistryService)
    service.update_dataset.return_value = _make_dataset()

    client = _make_app_with_service(service)
    response = client.put("/api/v1/datasets/d-1", json={"description": "only this"})

    assert response.status_code == 200
    kwargs = service.update_dataset.call_args.kwargs
    assert kwargs["organization"] is None
    assert kwargs["organisms"] is None
    assert kwargs["license"] is None
    assert kwargs["authors"] is None


def test_list_datasets_response_includes_new_fields() -> None:
    """GET /datasets results include updated_at and all new Resource fields."""
    service = MagicMock(spec=RegistryService)
    service.list_datasets.return_value = [_make_dataset()]

    client = _make_app_with_service(service)
    response = client.get("/api/v1/datasets")

    item = response.json()["results"][0]
    assert "updated_at" in item
    assert "authors" in item
    assert "organization" in item
    assert "contact_email" in item
    assert "publications" in item
    assert "funding" in item
    assert "model_scales" in item
    assert "organisms" in item
    assert "domains" in item
    assert "date_published" in item
    assert "digest_sha256" in item
    assert "size_bytes" in item
    assert "external_ids" in item
    assert "license" in item
    assert "metadata" in item

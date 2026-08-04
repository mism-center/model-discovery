from datetime import UTC, datetime
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from mism_registry.enums import (
    ExecutionType,
    ResourceRegistrationStatus,
    ResourceType,
    ResourceVersionStatus,
)
from mism_registry.resource import Resource
from mism_registry.search import SearchResult

from mismapi.core.deps import _get_registry_service
from mismapi.main import create_app
from mismapi.services.registry_service import RegistryService
from tests.conftest import override_anonymous, override_principal


def _make_resource(
    *,
    id: str = "r-1",
    name: str = "Example Model",
    description: str = "A test model",
    owner: str = "user-1",
    registration_status: ResourceRegistrationStatus = ResourceRegistrationStatus.APPROVED,
) -> Resource:
    return Resource(
        id=id,
        name=name,
        resource_type=ResourceType.MODEL,
        location_uri="https://example.com/model",
        execution_type=ExecutionType.DOCKER,
        description=description,
        version="1.0",
        version_status=ResourceVersionStatus.ACTIVE,
        owner=owner,
        registration_status=registration_status,
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
    )


def _make_app_with_service(service: RegistryService) -> TestClient:
    app = create_app()
    override_principal(app)
    app.dependency_overrides[_get_registry_service] = lambda: service
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
        registration_status=None,
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
        registration_status=None,
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
        registration_status=None,
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
    assert item["status"] == ResourceVersionStatus.ACTIVE.value
    assert item["owner"] == "user-1"
    assert item["description"] == "A test model"
    assert "created_at" in item


# ── POST /search — new fields ─────────────────────────────────────


def _make_search_result(resources: list[Resource]) -> SearchResult:
    return SearchResult(resources=resources, total=len(resources), scores=None, aggs={})


def test_search_result_includes_all_new_fields() -> None:
    """POST /search result items expose all Resource fields."""
    service = MagicMock(spec=RegistryService)
    service.search.return_value = _make_search_result([_make_resource()])

    client = _make_app_with_service(service)
    response = client.post("/api/v1/search", json={})

    assert response.status_code == 200
    item = response.json()["results"][0]

    # New attribution fields
    assert "authors" in item
    assert "organization" in item
    assert "contact_email" in item
    assert "publications" in item
    assert "funding" in item
    # New scientific fields
    assert "model_scales" in item
    assert "domains" in item
    assert "date_published" in item
    # New integrity fields
    assert "digest_sha256" in item
    assert "size_bytes" in item
    assert "external_ids" in item
    assert "license" in item
    # New execution fields
    assert "execution_ref" in item
    assert "io_spec" in item
    # System
    assert "metadata" in item
    assert "updated_at" in item


def test_search_result_new_fields_default_correctly() -> None:
    """New fields default to empty/None when not set on Resource."""
    service = MagicMock(spec=RegistryService)
    service.search.return_value = _make_search_result([_make_resource()])

    client = _make_app_with_service(service)
    response = client.post("/api/v1/search", json={})

    assert response.status_code == 200
    item = response.json()["results"][0]

    assert item["authors"] == []
    assert item["publications"] == []
    assert item["funding"] == []
    assert item["organization"] == ""
    assert item["contact_email"] == ""
    assert item["model_scales"] == []
    assert item["domains"] == []
    assert item["date_published"] is None
    assert item["digest_sha256"] == ""
    assert item["size_bytes"] is None
    assert item["external_ids"] == {}
    assert item["license"] == ""
    assert item["execution_ref"] == ""
    assert item["io_spec"] is None
    assert item["metadata"] == {}


def test_search_result_with_rich_resource() -> None:
    """POST /search correctly serializes a fully-populated Resource."""
    from mism_registry.types import Author, IOSlot, IOSpec, Publication

    resource = Resource(
        id="r-rich",
        name="Rich Model",
        resource_type=ResourceType.MODEL,
        location_uri="https://example.com/rich",
        execution_type=ExecutionType.DOCKER,
        execution_ref="docker://rich:1",
        description="Fully populated",
        version="2.0",
        version_status=ResourceVersionStatus.ACTIVE,
        owner="user-1",
        authors=[
            Author(name="Jane", orcid="0000-0001-2345-6789", affiliation="RENCI", role="lead")
        ],
        organization="RENCI",
        contact_email="jane@renci.org",
        publications=[Publication(title="Paper", doi="10.1/x")],
        funding=["NIH"],
        model_scales=["cellular"],
        organisms=["human"],
        domains=["cardiology"],
        io_spec=IOSpec(
            inputs=(IOSlot(name="v", tags=("scalar",)),),
            outputs=(IOSlot(name="i"),),
        ),
        digest_sha256="abc",
        size_bytes=1024,
        external_ids={"biomodels": "M001"},
        license="MIT",
        metadata={"key": "value"},
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
    )
    service = MagicMock(spec=RegistryService)
    service.search.return_value = _make_search_result([resource])

    client = _make_app_with_service(service)
    response = client.post("/api/v1/search", json={})

    assert response.status_code == 200
    item = response.json()["results"][0]

    assert item["authors"] == [
        {"name": "Jane", "orcid": "0000-0001-2345-6789", "affiliation": "RENCI", "role": "lead"}
    ]
    assert item["organization"] == "RENCI"
    assert item["contact_email"] == "jane@renci.org"
    assert item["publications"] == [
        {"title": "Paper", "doi": "10.1/x", "pmid": "", "url": "", "citation": ""}
    ]
    assert item["funding"] == ["NIH"]
    assert item["model_scales"] == ["cellular"]
    assert item["organisms"] == ["human"]
    assert item["domains"] == ["cardiology"]
    assert item["execution_ref"] == "docker://rich:1"
    assert item["io_spec"]["inputs"][0]["name"] == "v"
    assert item["io_spec"]["inputs"][0]["tags"] == ["scalar"]
    assert item["io_spec"]["outputs"][0]["name"] == "i"
    assert item["digest_sha256"] == "abc"
    assert item["size_bytes"] == 1024
    assert item["external_ids"] == {"biomodels": "M001"}
    assert item["license"] == "MIT"
    assert item["metadata"] == {"key": "value"}


def test_list_models_response_includes_new_fields() -> None:
    """GET /models results include all new Resource fields."""
    service = MagicMock(spec=RegistryService)
    service.list_models.return_value = [_make_resource()]

    client = _make_app_with_service(service)
    response = client.get("/api/v1/models")

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
    assert "execution_ref" in item
    assert "io_spec" in item
    assert "metadata" in item


# ── Visibility gate on the list endpoint ─────────────────────────────
#
# GET /models/{id} and the search path both restrict unapproved models to their
# owner. The list endpoint did not, so a draft model's name, description and
# owner were still enumerable by an anonymous caller even though its detail page
# 404'd.


def _anonymous_client(service: RegistryService) -> TestClient:
    app = create_app()
    override_anonymous(app)
    app.dependency_overrides[_get_registry_service] = lambda: service
    return TestClient(app)


def test_list_models_hides_unapproved_from_anonymous_callers() -> None:
    service = MagicMock(spec=RegistryService)
    service.list_models.return_value = [
        _make_resource(id="approved", name="Public"),
        _make_resource(
            id="draft",
            name="Secret",
            registration_status=ResourceRegistrationStatus.DRAFT,
        ),
    ]

    response = _anonymous_client(service).get("/api/v1/models")

    assert response.status_code == 200
    payload = response.json()
    assert [r["id"] for r in payload["results"]] == ["approved"]
    # `total` must reflect the filtered set — a count of 2 would betray the
    # hidden model's existence on its own.
    assert payload["total"] == 1


def test_list_models_shows_owner_their_own_unapproved_models() -> None:
    service = MagicMock(spec=RegistryService)
    service.list_models.return_value = [
        _make_resource(
            id="mine",
            owner="user-1",
            registration_status=ResourceRegistrationStatus.PENDING_REVIEW,
        ),
        _make_resource(
            id="theirs",
            owner="someone-else",
            registration_status=ResourceRegistrationStatus.PENDING_REVIEW,
        ),
    ]

    # override_principal installs subject "user-1".
    response = _make_app_with_service(service).get("/api/v1/models")

    assert response.status_code == 200
    assert [r["id"] for r in response.json()["results"]] == ["mine"]


def test_list_models_pagination_applies_after_the_visibility_filter() -> None:
    service = MagicMock(spec=RegistryService)
    service.list_models.return_value = [
        _make_resource(id="draft", registration_status=ResourceRegistrationStatus.DRAFT),
        _make_resource(id="a"),
        _make_resource(id="b"),
    ]

    response = _anonymous_client(service).get("/api/v1/models?limit=1&offset=0")

    assert response.status_code == 200
    payload = response.json()
    # Without filter-before-paginate the hidden draft would consume the page and
    # return an empty result set for a page the client was told exists.
    assert [r["id"] for r in payload["results"]] == ["a"]
    assert payload["total"] == 2

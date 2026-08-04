from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from mism_registry.enums import (
    ExecutionType,
    ResourceRegistrationStatus,
    ResourceType,
    ResourceVersionStatus,
)
from mism_registry.resource import Resource

from mismapi.core.deps import _get_registry_service
from mismapi.main import create_app
from mismapi.services.registry_service import RegistryService
from tests.conftest import minimal_oidc_settings, override_anonymous, override_principal


def _make_model(
    *,
    id: str = "m-1",
    name: str = "Example Model",
    description: str = "A test model",
    owner: str = "user-1",
    execution_type: ExecutionType = ExecutionType.PYTHON,
    execution_ref: str = "",
    version: str = "0.1.0",
    registration_status: ResourceRegistrationStatus = ResourceRegistrationStatus.APPROVED,
) -> Resource:
    return Resource(
        id=id,
        name=name,
        resource_type=ResourceType.MODEL,
        location_uri="irods:///models/m-1",
        execution_type=execution_type,
        execution_ref=execution_ref,
        description=description,
        version=version,
        version_status=ResourceVersionStatus.ACTIVE,
        registration_status=registration_status,
        owner=owner,
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


# ── POST /models ─────────────────────────────────────────────────


def test_create_model_success() -> None:
    service = MagicMock(spec=RegistryService)
    service.create_model.return_value = _make_model()

    client = _make_app_with_service(service)
    response = client.post(
        "/api/v1/models",
        json={
            "name": "Example Model",
            "location_uri": "irods:///models/m-1",
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


def test_create_model_missing_name_returns_400() -> None:
    service = MagicMock(spec=RegistryService)
    client = _make_app_with_service(service)

    response = client.post(
        "/api/v1/models",
        json={
            "location_uri": "irods:///models/m-1",
            "execution_type": "python",
        },
    )

    assert response.status_code == 400
    service.create_model.assert_not_called()


def test_create_model_missing_execution_type_returns_400() -> None:
    service = MagicMock(spec=RegistryService)
    client = _make_app_with_service(service)

    response = client.post(
        "/api/v1/models",
        json={
            "name": "Example Model",
            "location_uri": "irods:///models/m-1",
        },
    )

    assert response.status_code == 400
    service.create_model.assert_not_called()


def test_create_model_invalid_execution_type_returns_422() -> None:
    service = MagicMock(spec=RegistryService)
    client = _make_app_with_service(service)

    response = client.post(
        "/api/v1/models",
        json={
            "name": "Example Model",
            "location_uri": "irods:///models/m-1",
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
            "location_uri": "irods:///models/m-1",
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
            "location_uri": "irods:///models/m-1",
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
            "location_uri": "irods:///models/m-1",
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
            "location_uri": "irods:///models/m-1",
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


# ── New Resource fields ───────────────────────────────────────────


def test_create_model_forwards_attribution_fields() -> None:
    """POST /models passes authors, org, publications, funding to service."""
    service = MagicMock(spec=RegistryService)
    service.create_model.return_value = _make_model()

    client = _make_app_with_service(service)
    response = client.post(
        "/api/v1/models",
        json={
            "name": "Bio Model",
            "location_uri": "irods:///models/bio",
            "execution_type": "docker",
            "authors": [
                {
                    "name": "Jane Doe",
                    "orcid": "0000-0001-2345-6789",
                    "affiliation": "RENCI",
                    "role": "lead",
                }
            ],
            "organization": "RENCI",
            "contact_email": "jane@renci.org",
            "publications": [{"title": "My Paper", "doi": "10.1/x", "url": "", "citation": ""}],
            "funding": ["NIH R01"],
        },
    )

    assert response.status_code == 201
    kwargs = service.create_model.call_args.kwargs
    assert kwargs["organization"] == "RENCI"
    assert kwargs["contact_email"] == "jane@renci.org"
    assert kwargs["funding"] == ["NIH R01"]
    assert len(kwargs["authors"]) == 1
    assert kwargs["authors"][0].name == "Jane Doe"
    assert len(kwargs["publications"]) == 1
    assert kwargs["publications"][0].title == "My Paper"


def test_create_model_forwards_scientific_fields() -> None:
    """POST /models passes model_scales, organisms, domains, date_published to service."""
    service = MagicMock(spec=RegistryService)
    service.create_model.return_value = _make_model()

    client = _make_app_with_service(service)
    response = client.post(
        "/api/v1/models",
        json={
            "name": "Sci Model",
            "location_uri": "irods:///models/sci",
            "execution_type": "python",
            "model_scales": ["cellular", "tissue"],
            "organisms": ["human"],
            "domains": ["cardiology"],
            "date_published": "2024-06-01",
        },
    )

    assert response.status_code == 201
    kwargs = service.create_model.call_args.kwargs
    assert kwargs["model_scales"] == ["cellular", "tissue"]
    assert kwargs["organisms"] == ["human"]
    assert kwargs["domains"] == ["cardiology"]
    assert str(kwargs["date_published"]) == "2024-06-01"


def test_create_model_forwards_integrity_fields() -> None:
    """POST /models passes digest_sha256, size_bytes, external_ids, license to service."""
    service = MagicMock(spec=RegistryService)
    service.create_model.return_value = _make_model()

    client = _make_app_with_service(service)
    response = client.post(
        "/api/v1/models",
        json={
            "name": "Integrity Model",
            "location_uri": "irods:///models/ig",
            "execution_type": "docker",
            "digest_sha256": "abc123",
            "size_bytes": 4096,
            "external_ids": {"biomodels": "MODEL001"},
            "license": "MIT",
        },
    )

    assert response.status_code == 201
    kwargs = service.create_model.call_args.kwargs
    assert kwargs["digest_sha256"] == "abc123"
    assert kwargs["size_bytes"] == 4096
    assert kwargs["external_ids"] == {"biomodels": "MODEL001"}
    assert kwargs["license"] == "MIT"


def test_create_model_forwards_io_spec() -> None:
    """POST /models converts IOSpecDTO to IOSpec dataclass before calling service."""
    service = MagicMock(spec=RegistryService)
    service.create_model.return_value = _make_model()

    client = _make_app_with_service(service)
    response = client.post(
        "/api/v1/models",
        json={
            "name": "IOSpec Model",
            "location_uri": "irods:///models/io",
            "execution_type": "docker",
            "io_spec": {
                "inputs": [
                    {"name": "voltage", "tags": ["scalar"], "required": True, "description": ""}
                ],
                "outputs": [{"name": "current", "tags": [], "required": True, "description": ""}],
            },
        },
    )

    assert response.status_code == 201
    kwargs = service.create_model.call_args.kwargs
    io = kwargs["io_spec"]
    assert io is not None
    assert io.inputs[0].name == "voltage"
    assert io.outputs[0].name == "current"


def test_create_model_response_includes_new_fields() -> None:
    """POST /models response contains updated_at, metadata, and all new fields."""
    resource = _make_model()
    service = MagicMock(spec=RegistryService)
    service.create_model.return_value = resource

    client = _make_app_with_service(service)
    response = client.post(
        "/api/v1/models",
        json={
            "name": "New Fields Model",
            "location_uri": "irods:///models/nf",
            "execution_type": "python",
        },
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
    assert "io_spec" in payload


def test_update_model_forwards_new_fields() -> None:
    """PUT /models/{id} passes all new fields to service when present."""
    service = MagicMock(spec=RegistryService)
    service.update_model.return_value = _make_model()

    client = _make_app_with_service(service)
    response = client.put(
        "/api/v1/models/m-1",
        json={
            "organization": "New Org",
            "contact_email": "new@org.com",
            "organisms": ["zebrafish"],
            "license": "Apache-2.0",
            "digest_sha256": "newdigest",
            "size_bytes": 8192,
            "funding": ["DOE"],
        },
    )

    assert response.status_code == 200
    kwargs = service.update_model.call_args.kwargs
    assert kwargs["organization"] == "New Org"
    assert kwargs["contact_email"] == "new@org.com"
    assert kwargs["organisms"] == ["zebrafish"]
    assert kwargs["license"] == "Apache-2.0"
    assert kwargs["digest_sha256"] == "newdigest"
    assert kwargs["size_bytes"] == 8192
    assert kwargs["funding"] == ["DOE"]


def test_update_model_omitted_new_fields_are_none() -> None:
    """PUT /models/{id} omitting new fields passes None (no-op sentinel) to service."""
    service = MagicMock(spec=RegistryService)
    service.update_model.return_value = _make_model()

    client = _make_app_with_service(service)
    response = client.put("/api/v1/models/m-1", json={"description": "only this"})

    assert response.status_code == 200
    kwargs = service.update_model.call_args.kwargs
    assert kwargs["organization"] is None
    assert kwargs["organisms"] is None
    assert kwargs["license"] is None
    assert kwargs["authors"] is None
    assert kwargs["io_spec"] is None


# ── GET /models/{id} detail view ────────────────────────────────


def test_get_model_detail_includes_characterization_fields() -> None:
    import dataclasses

    from mism_registry.types import (
        Argument,
        Compute,
        Container,
        Dependency,
        EntryPoint,
        TestSpec,
    )

    resource = dataclasses.replace(
        _make_model(),
        short_description="short",
        model_class=["ODE model"],
        formalism=["KISAO:0000019"],
        determinism="deterministic",
        time_dynamics="continuous",
        spatial="non-spatial",
        multiscale=True,
        infectious_agents=["SARS-CoV-2"],
        proteins_genes=["ACE2"],
        execution_status="characterized",
        language_name="python",
        language_version=">=3.11",
        execution_notes="notes",
        dependencies=[Dependency(name="numpy", version_constraint=">=1.0", kind="runtime")],
        containers=[Container(kind="docker", file="Dockerfile", image_name="model:latest")],
        compute=Compute(cpu_cores=4, memory_gb=8.0, gpu_required=False),
        entry_points=[
            EntryPoint(
                command="python run.py",
                purpose="run",
                arguments=(Argument(name="--seed", description="rng seed", default=0),),
            )
        ],
        tests=TestSpec(framework="pytest", invocation="pytest -q"),
    )

    service = MagicMock(spec=RegistryService)
    service.get_model.return_value = resource

    client = _make_app_with_service(service)
    response = client.get("/api/v1/models/m-1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["short_description"] == "short"
    assert payload["model_class"] == ["ODE model"]
    assert payload["determinism"] == "deterministic"
    assert payload["multiscale"] is True
    assert payload["infectious_agents"] == ["SARS-CoV-2"]
    assert payload["language_name"] == "python"
    assert payload["execution_status"] == "characterized"
    assert payload["dependencies"][0]["name"] == "numpy"
    assert payload["containers"][0]["kind"] == "docker"
    assert payload["compute"]["cpu_cores"] == 4
    assert payload["entry_points"][0]["command"] == "python run.py"
    assert payload["entry_points"][0]["arguments"][0]["name"] == "--seed"
    assert payload["tests"]["framework"] == "pytest"
    service.get_model.assert_called_once_with("m-1")


def test_get_model_detail_empty_characterization_defaults() -> None:
    service = MagicMock(spec=RegistryService)
    service.get_model.return_value = _make_model()

    client = _make_app_with_service(service)
    response = client.get("/api/v1/models/m-1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["dependencies"] == []
    assert payload["containers"] == []
    assert payload["compute"] is None
    assert payload["tests"] is None
    assert payload["determinism"] == "unknown"


# ── GET /models/{id} visibility ──────────────────────────────────
# approved models are public; anything still in the registration workflow
# (draft/annotating/pending_review/rejected) is visible only to its owner.
# A mismatch must 404 (not 403) so the endpoint isn't an id oracle.


@pytest.mark.parametrize(
    "registration_status",
    [
        ResourceRegistrationStatus.DRAFT,
        ResourceRegistrationStatus.ANNOTATING,
        ResourceRegistrationStatus.PENDING_REVIEW,
        ResourceRegistrationStatus.REJECTED,
    ],
)
def test_get_model_detail_unapproved_model_404s_for_anonymous_caller(
    registration_status: ResourceRegistrationStatus,
) -> None:
    service = MagicMock(spec=RegistryService)
    service.get_model.return_value = _make_model(
        owner="user-1", registration_status=registration_status
    )

    client = _make_app_with_service(service, authenticated=False)
    response = client.get("/api/v1/models/m-1")

    assert response.status_code == 404


@pytest.mark.parametrize(
    "registration_status",
    [
        ResourceRegistrationStatus.DRAFT,
        ResourceRegistrationStatus.ANNOTATING,
        ResourceRegistrationStatus.PENDING_REVIEW,
        ResourceRegistrationStatus.REJECTED,
    ],
)
def test_get_model_detail_unapproved_model_404s_for_non_owner(
    registration_status: ResourceRegistrationStatus,
) -> None:
    service = MagicMock(spec=RegistryService)
    service.get_model.return_value = _make_model(
        owner="someone-else", registration_status=registration_status
    )

    # override_principal defaults to subject "user-1" — not the owner above.
    client = _make_app_with_service(service, authenticated=True)
    response = client.get("/api/v1/models/m-1")

    assert response.status_code == 404


def test_get_model_detail_unapproved_model_visible_to_owner() -> None:
    service = MagicMock(spec=RegistryService)
    service.get_model.return_value = _make_model(
        owner="user-1", registration_status=ResourceRegistrationStatus.PENDING_REVIEW
    )

    # override_principal's default principal subject is "user-1" — the owner.
    client = _make_app_with_service(service, authenticated=True)
    response = client.get("/api/v1/models/m-1")

    assert response.status_code == 200
    assert response.json()["id"] == "m-1"


def test_get_model_detail_approved_model_visible_anonymously() -> None:
    service = MagicMock(spec=RegistryService)
    service.get_model.return_value = _make_model(
        owner="user-1", registration_status=ResourceRegistrationStatus.APPROVED
    )

    client = _make_app_with_service(service, authenticated=False)
    response = client.get("/api/v1/models/m-1")

    assert response.status_code == 200
    assert response.json()["id"] == "m-1"


# ── metadata-package raw review ─────────────────────────────────


def test_get_metadata_package_raw_returns_sections() -> None:
    service = MagicMock(spec=RegistryService)
    service.read_metadata_package_raw.return_value = [
        ("metadata.yaml", "model:\n  name: x\n"),
        ("execution.yaml", "execution:\n  status: ok\n"),
    ]

    client = _make_app_with_service(service)
    response = client.get("/api/v1/models/m-1/metadata-package/raw")

    assert response.status_code == 200
    payload = response.json()
    assert payload["model_id"] == "m-1"
    assert [f["filename"] for f in payload["files"]] == ["metadata.yaml", "execution.yaml"]
    assert payload["files"][0]["content"] == "model:\n  name: x\n"
    service.read_metadata_package_raw.assert_called_once_with("m-1")


def test_update_metadata_package_raw_forwards_files() -> None:
    service = MagicMock(spec=RegistryService)
    service.write_metadata_package_raw.return_value = [
        ("metadata.yaml", "model:\n  name: edited\n"),
        ("execution.yaml", "execution:\n  status: ok\n"),
    ]

    client = _make_app_with_service(service)
    response = client.put(
        "/api/v1/models/m-1/metadata-package/raw",
        json={"files": [{"filename": "metadata.yaml", "content": "model:\n  name: edited\n"}]},
    )

    assert response.status_code == 200
    assert response.json()["files"][0]["content"] == "model:\n  name: edited\n"
    kwargs = service.write_metadata_package_raw.call_args.kwargs
    assert kwargs["model_id"] == "m-1"
    assert kwargs["files"] == [("metadata.yaml", "model:\n  name: edited\n")]


def test_update_metadata_package_raw_requires_files() -> None:
    service = MagicMock(spec=RegistryService)
    client = _make_app_with_service(service)

    response = client.put("/api/v1/models/m-1/metadata-package/raw", json={"files": []})

    assert response.status_code == 400  # app maps request validation errors to 400
    service.write_metadata_package_raw.assert_not_called()


# ── location_uri validation ────────────────────────────────────
# The download endpoint can only resolve iRODS URIs and plain paths.
# Create/update must reject everything else up front so the failure mode is
# obvious instead of surfacing as a 400 at download time.


@pytest.mark.parametrize(
    "bad_uri",
    [
        "http://localhost:8000/api/v1/models/foo",
        "https://example.com/model",
        "s3://bucket/key",
        "docker://foo:1",
        "git+https://example.com/model.git",
    ],
)
def test_create_model_rejects_unsupported_location_uri_scheme(bad_uri: str) -> None:
    service = MagicMock(spec=RegistryService)
    client = _make_app_with_service(service)

    response = client.post(
        "/api/v1/models",
        json={
            "name": "Example Model",
            "location_uri": bad_uri,
            "execution_type": "python",
        },
    )

    assert response.status_code == 400
    service.create_model.assert_not_called()


@pytest.mark.parametrize(
    "good_uri",
    [
        "irods:///models/m-1",
        "irods://models/m-1",
        "/models/m-1",
        "models/m-1",
        "",  # empty allowed — upload flow stamps the real URI in post-finish
    ],
)
def test_create_model_accepts_supported_location_uri_shapes(good_uri: str) -> None:
    service = MagicMock(spec=RegistryService)
    service.create_model.return_value = _make_model()

    client = _make_app_with_service(service)
    response = client.post(
        "/api/v1/models",
        json={
            "name": "Example Model",
            "location_uri": good_uri,
            "execution_type": "python",
        },
    )

    assert response.status_code == 201, response.text
    service.create_model.assert_called_once()


def test_update_model_rejects_unsupported_location_uri_scheme() -> None:
    service = MagicMock(spec=RegistryService)
    client = _make_app_with_service(service)

    response = client.put(
        "/api/v1/models/m-1",
        json={"location_uri": "https://example.com/model"},
    )

    assert response.status_code == 400
    service.update_model.assert_not_called()


def test_update_model_omitted_location_uri_is_no_op() -> None:
    """PUT without location_uri keeps the validator a no-op (None passes through)."""
    service = MagicMock(spec=RegistryService)
    service.update_model.return_value = _make_model()

    client = _make_app_with_service(service)
    response = client.put("/api/v1/models/m-1", json={"description": "x"})

    assert response.status_code == 200
    assert service.update_model.call_args.kwargs["location_uri"] is None

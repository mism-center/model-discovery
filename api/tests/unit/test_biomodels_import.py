"""Tests for the BioModels import service.

The registry is a real ``RegistryService`` over ``InMemoryRegistry`` so the
create / find / mark-complete / delete sequence genuinely runs; only the two
network clients are mocked.
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from mism_registry.enums import ResourceRegistrationStatus
from mism_registry.in_memory import InMemoryRegistry

from mismapi.auth.principal import AuthenticatedPrincipal
from mismapi.clients.biomodels_client import BioModelsArchive, BioModelsClient
from mismapi.clients.execution_client import ExecutionClient
from mismapi.core.errors import APIError
from mismapi.schemas.biomodels import BioModelsRecordDTO
from mismapi.services.biomodels_import import (
    MANIFEST_FILE,
    PACKAGE_DIR,
    import_biomodels_model,
)
from mismapi.services.registry_service import RegistryService
from tests.conftest import make_settings

_MODEL_ID = "BIOMD0000000732"
_RESOLVED_URL = (
    "https://www.biomodels.org/services/download/get-files/MODEL1006230038/6/MODEL1006230038.6.omex"
)


def _principal(subject: str = "user-1") -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(subject=subject, issuer="test", audience="mism-api", scopes=set())


def _zip_bytes(files: dict[str, str] | None = None) -> bytes:
    files = files or {"Kirschner_1998.xml": "<sbml/>", "manifest.xml": "<omexManifest/>"}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


def _record(**overrides: Any) -> BioModelsRecordDTO:
    values: dict[str, Any] = {
        "identifier": _MODEL_ID,
        "url": f"https://www.biomodels.org/{_MODEL_ID}",
        "name": "Kirschner1998 - Immunotherapy",
        "first_published": datetime(2010, 6, 23, tzinfo=UTC),
    }
    values.update(overrides)
    return BioModelsRecordDTO(**values)


def _registry_service() -> RegistryService:
    # The service commits the SQLAlchemy session after each mutation; the
    # in-memory registry persists on its own, so the session is inert here.
    return RegistryService(registry=InMemoryRegistry(), session=MagicMock())


def _biomodels_client(
    *,
    record: BioModelsRecordDTO | None = None,
    content: bytes | None = None,
    revision: str = "6",
) -> Any:
    client = AsyncMock(spec=BioModelsClient)
    client.get_model.return_value = record if record is not None else _record()
    client.download_archive.return_value = BioModelsArchive(
        content=content if content is not None else _zip_bytes(),
        revision=revision,
        resolved_url=_RESOLVED_URL,
    )
    return client


async def _import(
    tmp_path: Path,
    *,
    registry: RegistryService | None = None,
    biomodels: Any = None,
    execution: Any = None,
    model_id: str = _MODEL_ID,
    max_archive_bytes: int = 100 * 1024 * 1024,
    principal: AuthenticatedPrincipal | None = None,
) -> Any:
    return await import_biomodels_model(
        principal or _principal(),
        model_id=model_id,
        registry=registry if registry is not None else _registry_service(),
        biomodels=biomodels if biomodels is not None else _biomodels_client(),
        execution=execution if execution is not None else AsyncMock(spec=ExecutionClient),
        settings=make_settings(
            IRODS_MOUNT_PATH=str(tmp_path),
            BIOMODELS_MAX_ARCHIVE_BYTES=max_archive_bytes,
        ),
    )


# ── Happy path ───────────────────────────────────────────────────────


class TestSuccessfulImport:
    async def test_registers_a_draft_with_source_provenance(self, tmp_path: Path) -> None:
        imported = await _import(tmp_path)

        resource = imported.resource
        assert resource.registration_status == ResourceRegistrationStatus.DRAFT
        assert resource.source_repository == "biomodels"
        assert resource.source_identifier == _MODEL_ID
        assert resource.source_url == f"https://www.biomodels.org/{_MODEL_ID}"
        assert resource.source_revision == "6"

    async def test_extracts_the_archive_into_the_upload_directory(self, tmp_path: Path) -> None:
        imported = await _import(tmp_path)

        working_tree = tmp_path / imported.resource.id / "0.0.1"
        assert (working_tree / "Kirschner_1998.xml").read_text() == "<sbml/>"
        assert imported.files_extracted == 2

    async def test_marks_the_upload_complete(self, tmp_path: Path) -> None:
        registry = _registry_service()
        imported = await _import(tmp_path, registry=registry)

        stored = registry.get_model(imported.resource.id)
        assert stored.location_uri == f"{imported.resource.id}/0.0.1"
        assert stored.metadata["upload_status"] == "UPLOAD_COMPLETE"

    async def test_version_is_the_upload_default_not_the_biomodels_revision(
        self, tmp_path: Path
    ) -> None:
        """`version` is embedded in the storage path; the revision is not a version."""
        imported = await _import(tmp_path)
        assert imported.resource.version == "0.0.1"
        assert imported.resource.source_revision == "6"

    async def test_starts_annotation(self, tmp_path: Path) -> None:
        execution = AsyncMock(spec=ExecutionClient)
        imported = await _import(tmp_path, execution=execution)

        assert imported.annotation_started is True
        assert execution.annotate.await_args.kwargs["resource_id"] == imported.resource.id


# ── The manifest the annotation agent reads ──────────────────────────


class TestManifest:
    @staticmethod
    def _manifest(tmp_path: Path, imported: Any) -> dict[str, Any]:
        path = tmp_path / imported.resource.id / "0.0.1" / PACKAGE_DIR / MANIFEST_FILE
        loaded: dict[str, Any] = json.loads(path.read_text())
        return loaded

    async def test_written_under_the_metadata_package_directory(self, tmp_path: Path) -> None:
        imported = await _import(tmp_path)
        assert self._manifest(tmp_path, imported)["identifier"] == _MODEL_ID

    async def test_is_the_record_itself_not_a_wrapper_around_it(self, tmp_path: Path) -> None:
        """The file is the BioModels record; provenance lives in columns."""
        biomodels = _biomodels_client()
        record = await biomodels.get_model(_MODEL_ID)
        imported = await _import(tmp_path, biomodels=biomodels)

        assert self._manifest(tmp_path, imported) == record.model_dump(mode="json")

    async def test_carries_the_fields_the_agent_maps_from(self, tmp_path: Path) -> None:
        manifest = self._manifest(tmp_path, await _import(tmp_path))

        assert manifest["name"] == "Kirschner1998 - Immunotherapy"
        assert manifest["url"] == f"https://www.biomodels.org/{_MODEL_ID}"

    async def test_does_not_seed_a_metadata_yaml(self, tmp_path: Path) -> None:
        """Curated values are the agent's job; import only supplies the record."""
        imported = await _import(tmp_path)
        package_dir = tmp_path / imported.resource.id / "0.0.1" / PACKAGE_DIR
        assert [p.name for p in package_dir.iterdir()] == [MANIFEST_FILE]


# ── Fields approve does not overwrite ────────────────────────────────


class TestFieldsApproveDoesNotOverwrite:
    async def test_date_published_comes_from_first_published(self, tmp_path: Path) -> None:
        imported = await _import(tmp_path)
        assert imported.resource.date_published == datetime(2010, 6, 23, tzinfo=UTC).date()

    async def test_date_published_is_none_when_upstream_omits_it(self, tmp_path: Path) -> None:
        biomodels = _biomodels_client(record=_record(first_published=None))
        imported = await _import(tmp_path, biomodels=biomodels)
        assert imported.resource.date_published is None

    async def test_digest_and_size_describe_the_downloaded_archive(self, tmp_path: Path) -> None:
        content = _zip_bytes()
        biomodels = _biomodels_client(content=content)
        imported = await _import(tmp_path, biomodels=biomodels)

        assert imported.resource.digest_sha256 == hashlib.sha256(content).hexdigest()
        assert imported.resource.size_bytes == len(content)

    async def test_the_model_is_not_marked_executable(self, tmp_path: Path) -> None:
        """BioModels ships no run recipe and nothing has built an image, so a
        null execution_type is the truthful state until the annotator sets it."""
        imported = await _import(tmp_path)
        assert imported.resource.execution_type is None

    async def test_format_tags_are_left_for_the_annotation_agent(self, tmp_path: Path) -> None:
        """An OMEX archive holds SBML, SED-ML, CellML and more; the container
        format is not the resource's format."""
        imported = await _import(tmp_path)
        assert imported.resource.format_tags == []

    async def test_falls_back_to_the_model_id_when_upstream_has_no_name(
        self, tmp_path: Path
    ) -> None:
        biomodels = _biomodels_client(record=_record(name=""))
        imported = await _import(tmp_path, biomodels=biomodels)
        assert imported.resource.name == _MODEL_ID


# ── Rejections ───────────────────────────────────────────────────────


class TestRejections:
    async def test_non_biomodels_id_is_rejected_before_any_request(self, tmp_path: Path) -> None:
        biomodels = _biomodels_client()

        with pytest.raises(APIError) as excinfo:
            await _import(tmp_path, biomodels=biomodels, model_id="not-a-model")

        assert excinfo.value.status_code == 400
        assert excinfo.value.code == "biomodels_invalid_model_id"
        biomodels.get_model.assert_not_awaited()

    async def test_lowercase_ids_are_normalized_rather_than_rejected(self, tmp_path: Path) -> None:
        imported = await _import(tmp_path, model_id=_MODEL_ID.lower())
        assert imported.resource.source_identifier == _MODEL_ID

    async def test_duplicate_import_is_a_409_naming_the_existing_model(
        self, tmp_path: Path
    ) -> None:
        registry = _registry_service()
        first = await _import(tmp_path, registry=registry)

        with pytest.raises(APIError) as excinfo:
            await _import(tmp_path, registry=registry)

        assert excinfo.value.status_code == 409
        assert excinfo.value.code == "biomodels_already_imported"
        assert excinfo.value.meta is not None
        assert excinfo.value.meta["model_id"] == first.resource.id

    async def test_duplicate_is_detected_before_the_download(self, tmp_path: Path) -> None:
        registry = _registry_service()
        await _import(tmp_path, registry=registry)

        biomodels = _biomodels_client()
        with pytest.raises(APIError):
            await _import(tmp_path, registry=registry, biomodels=biomodels)

        biomodels.download_archive.assert_not_awaited()

    async def test_a_different_model_is_not_a_duplicate(self, tmp_path: Path) -> None:
        registry = _registry_service()
        await _import(tmp_path, registry=registry)

        other = "BIOMD0000000999"
        imported = await _import(
            tmp_path,
            registry=registry,
            biomodels=_biomodels_client(record=_record(identifier=other)),
            model_id=other,
        )
        assert imported.resource.source_identifier == other


# ── Failure handling ─────────────────────────────────────────────────


class TestFailureHandling:
    async def test_annotation_failure_leaves_the_import_standing(self, tmp_path: Path) -> None:
        execution = AsyncMock(spec=ExecutionClient)
        execution.annotate.side_effect = APIError(
            status_code=502, code="execution_unavailable", detail="down"
        )

        registry = _registry_service()
        imported = await _import(tmp_path, registry=registry, execution=execution)

        assert imported.annotation_started is False
        assert registry.get_model(imported.resource.id).id == imported.resource.id

    async def test_oversized_archive_leaves_no_model_behind(self, tmp_path: Path) -> None:
        registry = _registry_service()

        with pytest.raises(APIError) as excinfo:
            await _import(tmp_path, registry=registry, max_archive_bytes=1)

        assert excinfo.value.status_code == 413
        assert registry.find_by_source(repository="biomodels") == []

    async def test_oversized_archive_leaves_no_files_behind(self, tmp_path: Path) -> None:
        with pytest.raises(APIError):
            await _import(tmp_path, max_archive_bytes=1)

        assert list(tmp_path.iterdir()) == []

    async def test_a_failed_import_can_be_retried(self, tmp_path: Path) -> None:
        """Rollback must clear the source identifier, or the retry 409s."""
        registry = _registry_service()
        with pytest.raises(APIError):
            await _import(tmp_path, registry=registry, max_archive_bytes=1)

        imported = await _import(tmp_path, registry=registry)
        assert imported.resource.source_identifier == _MODEL_ID

    @staticmethod
    def _failing_registry() -> RegistryService:
        registry = _registry_service()
        registry.mark_upload_complete = MagicMock(  # type: ignore[method-assign]
            side_effect=APIError(status_code=400, code="boom", detail="boom")
        )
        return registry

    async def test_failure_after_extraction_removes_both_row_and_files(
        self, tmp_path: Path
    ) -> None:
        """The oversize path fails before anything is written; this one does not."""
        registry = self._failing_registry()

        with pytest.raises(APIError):
            await _import(tmp_path, registry=registry)

        assert registry.find_by_source(repository="biomodels") == []
        assert [p for p in tmp_path.rglob("*") if p.is_file()] == []

    async def test_rollback_leaves_other_versions_of_the_resource_alone(
        self, tmp_path: Path
    ) -> None:
        """Rollback owns the version directory it wrote, not the resource's tree."""
        registry = self._failing_registry()
        created: list[str] = []
        real_create = registry.create_model

        def capture(*args: Any, **kwargs: Any) -> Any:
            resource = real_create(*args, **kwargs)
            created.append(resource.id)
            # A sibling version, as a re-import or a second upload would leave.
            sibling = tmp_path / resource.id / "0.0.2"
            sibling.mkdir(parents=True)
            (sibling / "keep.txt").write_text("not this import's to delete")
            return resource

        registry.create_model = capture  # type: ignore[method-assign]

        with pytest.raises(APIError):
            await _import(tmp_path, registry=registry)

        resource_dir = tmp_path / created[0]
        assert not (resource_dir / "0.0.1").exists()
        assert (resource_dir / "0.0.2" / "keep.txt").read_text() == ("not this import's to delete")

"""Import a BioModels model into the registry as a DRAFT awaiting annotation.

An imported model runs the same onboarding path as a user upload: files land on
the iRODS PVC, an annotation run is fired, the agent writes a metadata-package,
and a human reviews and approves it.

The BioModels record is written to ``metadata-package/biomodels_metadata.json``
for the annotation agent to read. Nothing here mirrors those curated values
into columns: approving a model
overwrites them from the package the agent produces, so a value set at import
would be discarded. The exceptions are ``date_published``, ``digest_sha256`` and
``size_bytes``: approve does not touch those, so import is their only writer.

``format_tags`` is left empty despite also surviving approve. The archive is
OMEX, but its contents are not — a single import carries SBML, SED-ML, CellML,
MATLAB and more — so tagging the resource from the container format alone would
be both wrong and reductive. Determining it belongs to the annotation agent.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

from mism_registry.resource import Resource

from mismapi.auth.principal import AuthenticatedPrincipal
from mismapi.clients.biomodels_client import BioModelsClient
from mismapi.clients.execution_client import ExecutionClient
from mismapi.core.archive import ExtractedArchive, extract_zip
from mismapi.core.errors import APIError
from mismapi.core.settings import Settings
from mismapi.schemas.biomodels import BioModelsRecordDTO, normalize_model_id
from mismapi.services.registry_service import RegistryService
from mismapi.utils import upload_dir

logger = logging.getLogger(__name__)

SOURCE_REPOSITORY = "biomodels"
PACKAGE_DIR = "metadata-package"
MANIFEST_FILE = "biomodels_metadata.json"

# Mirrors ui/app/routes/upload.tsx: a fresh upload is 0.0.1 with a placeholder
# location_uri that mark_upload_complete rewrites. `version` is embedded in the
# storage path by `upload_dir`, so it must not carry the BioModels revision —
# that belongs in source_revision.
INITIAL_VERSION = "0.0.1"
PENDING_LOCATION_URI = "irods:///pending"

_NAME_MAX_LENGTH = 500


@dataclass(slots=True)
class ImportedModel:
    resource: Resource
    files_extracted: int
    size_bytes: int
    annotation_started: bool


async def import_biomodels_model(
    principal: AuthenticatedPrincipal,
    *,
    model_id: str,
    registry: RegistryService,
    biomodels: BioModelsClient,
    execution: ExecutionClient,
    settings: Settings,
) -> ImportedModel:
    """Register ``model_id`` from BioModels and start its annotation run.

    The duplicate check runs before the download so a re-import costs one cheap
    query rather than a full archive fetch. It is a read-then-write, so two
    concurrent imports of the same model can both pass it; the
    ``uq_resources_source`` unique index is what actually holds the line, and
    ``create_model`` turns that collision into the same 409.
    """
    normalized = normalize_model_id(model_id)
    if normalized is None:
        raise APIError(
            status_code=400,
            code="biomodels_invalid_model_id",
            detail=f"'{model_id}' is not a BioModels model id.",
        )

    _reject_duplicate(registry, normalized)

    record = await biomodels.get_model(normalized)
    archive = await biomodels.download_archive(normalized)

    resource = registry.create_model(
        principal,
        name=(record.name or normalized)[:_NAME_MAX_LENGTH],
        location_uri=PENDING_LOCATION_URI,
        # Null marks the model non-executable: BioModels ships no run recipe, and
        # nothing has built an image. The annotator sets it at approve time.
        execution_type=None,
        version=INITIAL_VERSION,
        date_published=record.first_published.date() if record.first_published else None,
        digest_sha256=hashlib.sha256(archive.content).hexdigest(),
        size_bytes=len(archive.content),
        source_repository=SOURCE_REPOSITORY,
        source_identifier=normalized,
        source_url=record.url,
        source_revision=archive.revision,
    )

    working_tree = Path(settings.irods_mount_path) / upload_dir(resource.id, resource.version)
    try:
        extracted = await asyncio.to_thread(
            _populate_working_tree,
            working_tree,
            content=archive.content,
            record=record,
            max_total_bytes=settings.biomodels_max_archive_bytes,
        )
        registry.mark_upload_complete(principal, resource_id=resource.id)
    except BaseException:
        # The row is already committed, so unwinding it is the only way to keep a
        # failed import from leaving a model whose files never arrived. Scoped to
        # the version directory this import wrote — its parent holds every version
        # of the resource, including siblings this import never owned.
        shutil.rmtree(working_tree, ignore_errors=True)
        try:
            registry.delete_model(principal, resource.id)
        except APIError:
            logger.exception("biomodels_import_rollback_failed model_id=%s", resource.id)
        raise

    logger.info(
        "biomodels_import model_id=%s source_identifier=%s revision=%s files=%d bytes=%d",
        resource.id,
        normalized,
        archive.revision,
        extracted.file_count,
        extracted.total_bytes,
    )

    annotation_started = await _start_annotation(execution, settings, resource_id=resource.id)

    return ImportedModel(
        resource=resource,
        files_extracted=extracted.file_count,
        size_bytes=extracted.total_bytes,
        annotation_started=annotation_started,
    )


def _reject_duplicate(registry: RegistryService, normalized: str) -> None:
    """Refuse an import of a model the registry already holds.

    Spans every owner and registration status, so the conflict may name a model
    the caller cannot see — an in-flight draft is exactly what this must catch.
    """
    existing = registry.find_by_source(
        repository=SOURCE_REPOSITORY,
        identifiers=[normalized],
    )
    if not existing:
        return

    match = existing[0]
    raise APIError(
        status_code=409,
        code="biomodels_already_imported",
        detail=f"{normalized} is already in the registry as model {match.id}.",
        meta={
            "model_id": match.id,
            "registration_status": match.registration_status.value,
            "source_identifier": normalized,
        },
    )


def _populate_working_tree(
    working_tree: Path,
    *,
    content: bytes,
    record: BioModelsRecordDTO,
    max_total_bytes: int,
) -> ExtractedArchive:
    extracted = extract_zip(io.BytesIO(content), working_tree, max_total_bytes=max_total_bytes)

    package_dir = working_tree / PACKAGE_DIR
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / MANIFEST_FILE).write_text(
        json.dumps(record.model_dump(mode="json"), indent=2, sort_keys=True), encoding="utf-8"
    )
    return extracted


async def _start_annotation(
    execution: ExecutionClient, settings: Settings, *, resource_id: str
) -> bool:
    """Fire the annotation run, reporting rather than raising on failure.

    The row and its files are already consistent at this point, so a failed
    start leaves a usable model the caller can retry with POST /runs/{id}.
    """
    try:
        await execution.annotate(
            resource_id=resource_id,
            image=settings.annotation_job_image,
            prompt=settings.annotation_job_prompt,
            cpus=settings.annotation_job_cpus,
            memory=settings.annotation_job_memory,
            openai_base_url=settings.annotation_openai_base_url,
            model=settings.annotation_model,
        )
    except APIError as exc:
        logger.warning(
            "biomodels_import_annotation_failed model_id=%s code=%s detail=%s",
            resource_id,
            exc.code,
            exc.detail,
        )
        return False
    return True

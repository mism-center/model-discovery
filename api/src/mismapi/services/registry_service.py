import logging
from datetime import date
from pathlib import Path
from typing import Any

from mism_registry import (
    ResourceNotFoundError,
    ResourceType,
    RunStatus,
    find_resources,
    get_model_run_details,
    prepare_run,
    register_dataset,
    register_model,
)
from mism_registry import (
    ValidationError as RegistryValidationError,
)
from mism_registry.backends.postgres import PostgresRegistry
from mism_registry.enums import ExecutionType
from mism_registry.protocol import Registry
from mism_registry.resource import Resource
from mism_registry.run import Run
from mism_registry.run_detail import ModelRunSummary
from mism_registry.search import (
    AGGREGATABLE_FIELDS,
    FILTERABLE_FIELDS,
    SearchQuery,
    SearchResult,
)
from mism_registry.types import Author, IOSpec, Publication
from sqlalchemy.orm import Session

from mismapi.auth.principal import AuthenticatedPrincipal
from mismapi.core.errors import APIError
from mismapi.core.file_storage import resolve_location_uri, safe_join
from mismapi.core.settings import get_settings

logger = logging.getLogger(__name__)


class RegistryService:
    """Orchestrates registry operations, session management, and (future) authz."""

    def __init__(self, registry: Registry, session: Session) -> None:
        self._registry = registry
        self._session = session

    # ── Model operations ─────────────────────────────────────────────

    def create_model(
        self,
        principal: AuthenticatedPrincipal,
        *,
        name: str,
        location_uri: str,
        execution_type: ExecutionType,
        execution_ref: str = "",
        io_spec: IOSpec | None = None,
        description: str = "",
        version: str = "",
        format_tags: list[str] | None = None,
        digest_sha256: str = "",
        size_bytes: int | None = None,
        external_ids: dict[str, str] | None = None,
        license: str = "",
        owner: str = "",
        metadata: dict[str, Any] | None = None,
        authors: list[Author] | None = None,
        organization: str = "",
        contact_email: str = "",
        publications: list[Publication] | None = None,
        funding: list[str] | None = None,
        modeling_scales: list[str] | None = None,
        organisms: list[str] | None = None,
        domains: list[str] | None = None,
        date_published: date | None = None,
    ) -> Resource:
        try:
            resource = register_model(
                self._registry,
                name=name,
                location_uri=location_uri,
                execution_type=execution_type,
                description=description,
                version=version,
                format_tags=format_tags or [],
                digest_sha256=digest_sha256,
                size_bytes=size_bytes,
                external_ids=external_ids or {},
                license=license,
                owner=owner or principal.subject,
                metadata=metadata or {},
                execution_ref=execution_ref,
                io_spec=io_spec,
                authors=authors or [],
                organization=organization,
                contact_email=contact_email,
                publications=publications or [],
                funding=funding or [],
                modeling_scales=modeling_scales or [],
                organisms=organisms or [],
                domains=domains or [],
                date_published=date_published,
            )
            # FUTURE: fga.write_tuple(user=principal.subject,
            #   relation="owner", object=f"model:{resource.id}")
            self._session.commit()
        except RegistryValidationError as exc:
            self._session.rollback()
            raise APIError(status_code=400, code="validation_error", detail=str(exc)) from exc

        logger.info("Registered model %s (%s) by %s", resource.id, resource.name, principal.subject)
        return resource

    def update_model(
        self,
        principal: AuthenticatedPrincipal,
        *,
        model_id: str,
        name: str | None = None,
        description: str | None = None,
        version: str | None = None,
        owner: str | None = None,
        location_uri: str | None = None,
        execution_type: ExecutionType | None = None,
        execution_ref: str | None = None,
        io_spec: IOSpec | None = None,
        format_tags: list[str] | None = None,
        digest_sha256: str | None = None,
        size_bytes: int | None = None,
        external_ids: dict[str, str] | None = None,
        license: str | None = None,
        metadata: dict[str, Any] | None = None,
        authors: list[Author] | None = None,
        organization: str | None = None,
        contact_email: str | None = None,
        publications: list[Publication] | None = None,
        funding: list[str] | None = None,
        modeling_scales: list[str] | None = None,
        organisms: list[str] | None = None,
        domains: list[str] | None = None,
        date_published: date | None = None,
    ) -> Resource:
        try:
            resource = self._registry.get_resource(model_id)
        except ResourceNotFoundError as exc:
            raise APIError(status_code=404, code="not_found", detail=str(exc)) from exc

        # FUTURE: fga.check(user=principal.subject,
        #   relation="editor", object=f"model:{model_id}")

        if name is not None:
            resource.name = name
        if description is not None:
            resource.description = description
        if version is not None:
            resource.version = version
        if owner is not None:
            resource.owner = owner
        if location_uri is not None:
            resource.location_uri = location_uri
        if execution_type is not None:
            resource.execution_type = execution_type
        if execution_ref is not None:
            resource.execution_ref = execution_ref
        if io_spec is not None:
            resource.io_spec = io_spec
        if format_tags is not None:
            resource.format_tags = format_tags
        if digest_sha256 is not None:
            resource.digest_sha256 = digest_sha256
        if size_bytes is not None:
            resource.size_bytes = size_bytes
        if external_ids is not None:
            resource.external_ids = external_ids
        if license is not None:
            resource.license = license
        if metadata is not None:
            resource.metadata = metadata
        if authors is not None:
            resource.authors = authors
        if organization is not None:
            resource.organization = organization
        if contact_email is not None:
            resource.contact_email = contact_email
        if publications is not None:
            resource.publications = publications
        if funding is not None:
            resource.funding = funding
        if modeling_scales is not None:
            resource.modeling_scales = modeling_scales
        if organisms is not None:
            resource.organisms = organisms
        if domains is not None:
            resource.domains = domains
        if date_published is not None:
            resource.date_published = date_published

        try:
            updated = self._registry.update_resource(resource)
            self._session.commit()
        except RegistryValidationError as exc:
            self._session.rollback()
            raise APIError(status_code=400, code="validation_error", detail=str(exc)) from exc

        logger.info("Updated model %s by %s", model_id, principal.subject)
        return updated

    # ── Run operations ───────────────────────────────────────────────

    def create_run(
        self,
        principal: AuthenticatedPrincipal,
        *,
        model_id: str,
        input_resource_ids: list[str] | None = None,
        parameters: dict[str, Any] | None = None,
        triggered_by: str = "",
        notes: str = "",
    ) -> Run:
        try:
            run = prepare_run(
                self._registry,
                model_id=model_id,
                input_resource_ids=input_resource_ids or [],
                parameters=parameters or {},
                triggered_by=triggered_by or principal.subject,
                notes=notes,
            )
            # FUTURE: fga.write_tuple(user=principal.subject,
            #   relation="owner", object=f"run:{run.id}")
            self._session.commit()
        except ResourceNotFoundError as exc:
            self._session.rollback()
            raise APIError(status_code=404, code="not_found", detail=str(exc)) from exc
        except RegistryValidationError as exc:
            self._session.rollback()
            raise APIError(status_code=400, code="validation_error", detail=str(exc)) from exc

        logger.info("Created run %s for model %s by %s", run.id, model_id, principal.subject)
        return run

    def get_run(self, run_id: str) -> tuple[Run, list[Resource], list[Resource]]:
        """Fetch a run plus its input/output resources, hydrated.

        Used by GET /runs/{run_id}. The endpoint is expected to call the
        Execution service first so the lazy DAL refresh has already run by the
        time we read the Run record here — guaranteeing fresh status.
        """
        try:
            run = self._registry.get_run(run_id)
        except ResourceNotFoundError as exc:
            raise APIError(status_code=404, code="not_found", detail=str(exc)) from exc

        # Hydrate input/output resources. Skip any that 404 — a run may
        # legitimately reference a resource that has since been deleted; we
        # don't want a single missing resource to blow up the whole response.
        input_resources: list[Resource] = []
        for rid in run.input_resource_ids:
            try:
                input_resources.append(self._registry.get_resource(rid))
            except ResourceNotFoundError:
                logger.warning("Run %s references missing input resource %s", run_id, rid)

        output_resources: list[Resource] = []
        for rid in run.output_resource_ids:
            try:
                output_resources.append(self._registry.get_resource(rid))
            except ResourceNotFoundError:
                logger.warning("Run %s references missing output resource %s", run_id, rid)

        return run, input_resources, output_resources

    # ── Resource file access ────────────────────────────────────────

    def get_resource_directory(self, resource_id: str) -> tuple[Resource, Path]:
        """Return the resource and its on-disk artifact directory.

        Raises APIError(404) if the resource isn't registered, or if the
        resolved directory doesn't exist on the iRODS mount. Raises
        APIError(400) for unsupported location_uri schemes / path traversal.
        """
        try:
            resource = self._registry.get_resource(resource_id)
        except ResourceNotFoundError as exc:
            raise APIError(status_code=404, code="not_found", detail=str(exc)) from exc

        mount = get_settings().irods_mount_path
        directory = resolve_location_uri(resource.location_uri, mount)
        if not directory.is_dir():
            raise APIError(
                status_code=400,
                code="not_a_directory",
                detail=(
                    f"Resource location_uri '{resource.location_uri}' resolves "
                    "to a file, not a directory; cannot list contents."
                ),
            )
        return resource, directory

    def resolve_resource_file(self, resource_id: str, rel_path: str) -> tuple[Resource, Path]:
        """Resolve a single file inside a resource's directory.

        Raises 404 (resource or file missing), 400 (bad path / traversal /
        not-a-file), or propagates the same errors as ``get_resource_directory``.
        """
        resource, directory = self.get_resource_directory(resource_id)
        return resource, safe_join(directory, rel_path)

    def get_model_run_details(
        self,
        *,
        model_id: str,
        status: RunStatus | None = None,
    ) -> ModelRunSummary:
        """Return the model plus all of its runs with hydrated I/O resources.

        Used by the UI's "Model Runs" page to populate the view in a single call.
        """
        try:
            return get_model_run_details(
                self._registry,
                model_id=model_id,
                status=status,
            )
        except ResourceNotFoundError as exc:
            raise APIError(status_code=404, code="not_found", detail=str(exc)) from exc
        except RegistryValidationError as exc:
            raise APIError(status_code=400, code="validation_error", detail=str(exc)) from exc

    # ── Query operations ─────────────────────────────────────────────

    def list_models(
        self,
        *,
        name_contains: str | None = None,
        owner: str | None = None,
        tags: list[str] | None = None,
        organisms: list[str] | None = None,
        scales: list[str] | None = None,
    ) -> list[Resource]:
        # FUTURE: batch fga check for visibility filtering
        return find_resources(
            self._registry,
            resource_type=ResourceType.MODEL,
            name_contains=name_contains,
            owner=owner,
            tags=tags,
            organisms=organisms,
            scales=scales,
        )

    # ── Search ────────────────────────────────────────────────────────

    def search(self, query: SearchQuery) -> SearchResult:
        """Validate and execute a full-text search with filters and aggregations."""
        # Validate filter fields and operators
        for f in query.filters:
            meta = FILTERABLE_FIELDS.get(f.field)
            if meta is None:
                raise APIError(
                    status_code=400,
                    code="invalid_filter",
                    detail=f"Unknown filter field: {f.field}",
                )
            _kind, allowed_ops = meta
            if f.op not in allowed_ops:
                raise APIError(
                    status_code=400,
                    code="invalid_filter",
                    detail=f"Operator '{f.op}' is not valid for field '{f.field}'. "
                    f"Allowed: {', '.join(sorted(allowed_ops))}",
                )

        # Validate aggregation fields
        for agg in query.agg_fields:
            if agg not in AGGREGATABLE_FIELDS:
                raise APIError(
                    status_code=400,
                    code="invalid_aggregation",
                    detail=f"Unknown aggregation field: {agg}",
                )

        if not isinstance(self._registry, PostgresRegistry):
            raise APIError(
                status_code=500,
                code="unsupported_backend",
                detail="Full-text search requires a PostgreSQL backend",
            )

        return self._registry.search_resources(query)

    # ── Dataset operations ─────────────────────────────────────────

    def create_dataset(
        self,
        principal: AuthenticatedPrincipal,
        *,
        name: str,
        location_uri: str,
        description: str = "",
        version: str = "",
        owner: str = "",
        format_tags: list[str] | None = None,
        digest_sha256: str = "",
        size_bytes: int | None = None,
        external_ids: dict[str, str] | None = None,
        license: str = "",
        metadata: dict[str, Any] | None = None,
        authors: list[Author] | None = None,
        organization: str = "",
        contact_email: str = "",
        publications: list[Publication] | None = None,
        funding: list[str] | None = None,
        modeling_scales: list[str] | None = None,
        organisms: list[str] | None = None,
        domains: list[str] | None = None,
        date_published: date | None = None,
    ) -> Resource:
        try:
            resource = register_dataset(
                self._registry,
                name=name,
                location_uri=location_uri,
                description=description,
                version=version,
                owner=owner or principal.subject,
                format_tags=format_tags or [],
                digest_sha256=digest_sha256,
                size_bytes=size_bytes,
                external_ids=external_ids or {},
                license=license,
                metadata=metadata or {},
                authors=authors or [],
                organization=organization,
                contact_email=contact_email,
                publications=publications or [],
                funding=funding or [],
                modeling_scales=modeling_scales or [],
                organisms=organisms or [],
                domains=domains or [],
                date_published=date_published,
            )
            # FUTURE: fga.write_tuple(user=principal.subject,
            #   relation="owner", object=f"dataset:{resource.id}")
            self._session.commit()
        except RegistryValidationError as exc:
            self._session.rollback()
            raise APIError(status_code=400, code="validation_error", detail=str(exc)) from exc

        logger.info(
            "Registered dataset %s (%s) by %s", resource.id, resource.name, principal.subject
        )
        return resource

    def update_dataset(
        self,
        principal: AuthenticatedPrincipal,
        *,
        dataset_id: str,
        name: str | None = None,
        description: str | None = None,
        version: str | None = None,
        owner: str | None = None,
        location_uri: str | None = None,
        format_tags: list[str] | None = None,
        digest_sha256: str | None = None,
        size_bytes: int | None = None,
        external_ids: dict[str, str] | None = None,
        license: str | None = None,
        metadata: dict[str, Any] | None = None,
        authors: list[Author] | None = None,
        organization: str | None = None,
        contact_email: str | None = None,
        publications: list[Publication] | None = None,
        funding: list[str] | None = None,
        modeling_scales: list[str] | None = None,
        organisms: list[str] | None = None,
        domains: list[str] | None = None,
        date_published: date | None = None,
    ) -> Resource:
        try:
            resource = self._registry.get_resource(dataset_id)
        except ResourceNotFoundError as exc:
            raise APIError(status_code=404, code="not_found", detail=str(exc)) from exc

        # FUTURE: fga.check(user=principal.subject,
        #   relation="editor", object=f"dataset:{dataset_id}")

        if name is not None:
            resource.name = name
        if description is not None:
            resource.description = description
        if version is not None:
            resource.version = version
        if owner is not None:
            resource.owner = owner
        if location_uri is not None:
            resource.location_uri = location_uri
        if format_tags is not None:
            resource.format_tags = format_tags
        if digest_sha256 is not None:
            resource.digest_sha256 = digest_sha256
        if size_bytes is not None:
            resource.size_bytes = size_bytes
        if external_ids is not None:
            resource.external_ids = external_ids
        if license is not None:
            resource.license = license
        if metadata is not None:
            resource.metadata = metadata
        if authors is not None:
            resource.authors = authors
        if organization is not None:
            resource.organization = organization
        if contact_email is not None:
            resource.contact_email = contact_email
        if publications is not None:
            resource.publications = publications
        if funding is not None:
            resource.funding = funding
        if modeling_scales is not None:
            resource.modeling_scales = modeling_scales
        if organisms is not None:
            resource.organisms = organisms
        if domains is not None:
            resource.domains = domains
        if date_published is not None:
            resource.date_published = date_published

        try:
            updated = self._registry.update_resource(resource)
            self._session.commit()
        except RegistryValidationError as exc:
            self._session.rollback()
            raise APIError(status_code=400, code="validation_error", detail=str(exc)) from exc

        logger.info("Updated dataset %s by %s", dataset_id, principal.subject)
        return updated

    def list_datasets(
        self,
        *,
        name_contains: str | None = None,
        owner: str | None = None,
        tags: list[str] | None = None,
        organisms: list[str] | None = None,
        scales: list[str] | None = None,
    ) -> list[Resource]:
        # FUTURE: batch fga check for visibility filtering
        return find_resources(
            self._registry,
            resource_type=ResourceType.DATASET,
            name_contains=name_contains,
            owner=owner,
            tags=tags,
            organisms=organisms,
            scales=scales,
        )

    # ── Upload lifecycle ─────────────────────────────────────────────

    def get_resource_and_assert_ownership(
        self,
        principal: AuthenticatedPrincipal,
        *,
        resource_id: str,
    ) -> Resource:
        """
        Look up `resource_id` and verify `principal` owns it.

        On any failure (resource missing OR caller is not the owner) raises a
        single, indistinguishable 403 with code `not_authorized`.

        FUTURE: replace string equality with `fga.check(user=principal.subject,
        relation="owner", object=f"resource:{resource_id}")`.
        """
        try:
            resource = self._registry.get_resource(resource_id)
        except ResourceNotFoundError:
            raise self._not_authorized_error() from None

        if resource.owner != principal.subject:
            raise self._not_authorized_error()
        return resource

    def mark_upload_complete(
        self,
        principal: AuthenticatedPrincipal,
        *,
        resource_id: str,
    ) -> Resource:
        """
        Stamp `metadata['upload_status'] = 'UPLOAD_COMPLETE'` on a resource owned by `principal`.

        Idempotent. Stored in `metadata` because `mism_registry.ResourceStatus`
        models publication lifecycle (active/superseded/archived), not content lifecycle.
        """
        resource = self.get_resource_and_assert_ownership(principal, resource_id=resource_id)

        new_metadata = dict(resource.metadata)
        new_metadata["upload_status"] = "UPLOAD_COMPLETE"
        resource.metadata = new_metadata

        try:
            updated = self._registry.update_resource(resource)
            self._session.commit()
        except RegistryValidationError as exc:
            self._session.rollback()
            raise APIError(status_code=400, code="validation_error", detail=str(exc)) from exc

        return updated

    @staticmethod
    def _not_authorized_error() -> APIError:
        """
        TODO: Improve error messages and handling by subclassing APIError with specific errors.
        That will help not only here but in many other places too.
        """
        return APIError(
            status_code=403,
            code="not_authorized",
            detail="Resource does not exist or principal is not its owner.",
        )

    # ── Lifecycle ────────────────────────────────────────────────────

    def close(self) -> None:
        self._session.close()

import dataclasses
import logging
import shutil
from datetime import date
from pathlib import Path
from typing import Any

import yaml
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
from mism_registry.enums import ExecutionType, ResourceRegistrationStatus
from mism_registry.protocol import Registry
from mism_registry.resource import Resource
from mism_registry.run import Run
from mism_registry.run_detail import ModelRunSummary
from mism_registry.search import (
    AGGREGATABLE_FIELDS,
    FILTERABLE_FIELDS,
    FieldFilter,
    SearchQuery,
    SearchResult,
)
from mism_registry.types import Author, IOSpec, Publication
from sqlalchemy.orm import Session

from mismapi.auth.principal import AuthenticatedPrincipal
from mismapi.core.errors import APIError
from mismapi.core.file_storage import resolve_location_uri, safe_join
from mismapi.core.settings import get_settings
from mismapi.services.metadata_package import (
    EXECUTION_FILE,
    METADATA_FILE,
    build_resource_from_package,
)
from mismapi.utils import upload_dir

logger = logging.getLogger(__name__)

# The metadata-package YAML files, in review/display order.
_PACKAGE_FILES = (METADATA_FILE, EXECUTION_FILE)


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
        model_scales: list[str] | None = None,
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
                model_scales=model_scales or [],
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

    def get_model(self, model_id: str) -> Resource:
        """Fetch a single model resource by ID, including registration_status."""
        try:
            return self._registry.get_resource(model_id)
        except ResourceNotFoundError as exc:
            raise APIError(status_code=404, code="not_found", detail=str(exc)) from exc

    def delete_model(
        self,
        principal: AuthenticatedPrincipal,
        model_id: str,
    ) -> None:
        """Delete a model: remove the DB record and wipe its on-disk directory."""
        resource = self.get_resource_and_assert_ownership(principal, resource_id=model_id)

        mount = get_settings().irods_mount_path
        try:
            directory = resolve_location_uri(resource.location_uri, mount)
            if directory.is_dir():
                shutil.rmtree(directory)
        except Exception:
            logger.warning(
                "Could not delete files for model %s at %s",
                model_id,
                resource.location_uri,
            )

        self._registry.delete_resource(model_id)  # type: ignore[attr-defined]  # added in local metadata-schema; remove once default-draft is synced
        self._session.commit()

    def list_annotating_models(self) -> list[Resource]:
        """Return all MODEL resources currently in ANNOTATING state.

        Used by the background poller to log status transitions.
        The postgres backend has no registration_status filter on find_resources,
        so we fetch all models and filter in-memory — safe because the
        ANNOTATING set is always small (O(1-10) in practice).
        """
        resources = find_resources(self._registry, resource_type=ResourceType.MODEL)
        return [
            r for r in resources if r.registration_status == ResourceRegistrationStatus.ANNOTATING
        ]

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
        model_scales: list[str] | None = None,
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
        if model_scales is not None:
            resource.model_scales = model_scales
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

    def _metadata_package_dir(self, model_id: str) -> Path:
        """Resolve ``<location_uri>/metadata-package/`` on the mount.

        Derives the path from ``model.location_uri`` (the authoritative on-disk
        path), not from ``upload_dir(model_id, model.version)``.
        ``write_metadata_package_raw`` syncs ``model.version`` from the annotation
        YAML, so the version field can diverge from the version segment embedded
        in ``location_uri`` after the first save — causing ``upload_dir``-based
        lookups to 404 while the download endpoint (which uses ``location_uri``
        directly) continues to work.
        Raises 404 if the model, the package dir, or either required YAML file
        is missing; 400 for unsupported schemes / path traversal.
        """
        try:
            model = self._registry.get_resource(model_id)
        except ResourceNotFoundError as exc:
            raise APIError(status_code=404, code="not_found", detail=str(exc)) from exc

        mount = get_settings().irods_mount_path
        # resolve_location_uri enforces the traversal check and that the dir exists.
        model_dir = resolve_location_uri(model.location_uri, mount)
        pkg_dir = model_dir / "metadata-package"
        if not pkg_dir.is_dir():
            raise APIError(
                status_code=404,
                code="metadata_package_not_found",
                detail=f"No metadata-package directory found for model {model_id}.",
            )
        missing = [f for f in (METADATA_FILE, EXECUTION_FILE) if not (pkg_dir / f).is_file()]
        if missing:
            raise APIError(
                status_code=404,
                code="metadata_package_not_found",
                detail=f"metadata-package for model {model_id} is missing {', '.join(missing)}.",
            )
        return pkg_dir

    def parse_metadata_package(self, model_id: str) -> Resource:
        """Parse the metadata-package for a model into a (transient) Resource.

        Reads ``metadata.yaml`` + ``execution.yaml`` and maps them onto a
        Resource. The result is *not* persisted — it's a preview of what the
        annotation package contains.

        Raises 404 (model / package / file missing) and 400 (malformed YAML).
        """
        pkg_dir = self._metadata_package_dir(model_id)
        try:
            return build_resource_from_package(pkg_dir)
        except (KeyError, ValueError, FileNotFoundError, yaml.YAMLError) as exc:
            raise APIError(
                status_code=400,
                code="invalid_metadata_package",
                detail=f"Could not parse metadata-package for model {model_id}: {exc}",
            ) from exc

    def read_metadata_package_raw(self, model_id: str) -> list[tuple[str, str]]:
        """Return the raw text of each metadata-package YAML file, in order.

        ``[(metadata.yaml, text), (execution.yaml, text)]`` — for the review view.
        Raises 404 if the model / package / files are missing.
        """
        pkg_dir = self._metadata_package_dir(model_id)
        return [(name, (pkg_dir / name).read_text(encoding="utf-8")) for name in _PACKAGE_FILES]

    def write_metadata_package_raw(
        self,
        principal: AuthenticatedPrincipal,
        *,
        model_id: str,
        files: list[tuple[str, str]],
    ) -> list[tuple[str, str]]:
        """Write edited raw YAML back to the metadata-package, then re-read it.

        Only the two known filenames are accepted (blocks path traversal), and
        each file must parse as YAML before anything is written (all-or-nothing).
        Returns the re-read raw files. Raises 403 (not owner), 404 (missing),
        400 (unknown filename or malformed YAML).
        """
        self.get_resource_and_assert_ownership(principal, resource_id=model_id)
        pkg_dir = self._metadata_package_dir(model_id)

        # Validate everything up front so a bad file never partially overwrites.
        for name, content in files:
            if name not in _PACKAGE_FILES:
                raise APIError(
                    status_code=400,
                    code="invalid_metadata_package",
                    detail=f"Unknown metadata-package file '{name}'. "
                    f"Allowed: {', '.join(_PACKAGE_FILES)}.",
                )
            try:
                yaml.safe_load(content)
            except yaml.YAMLError as exc:
                raise APIError(
                    status_code=400,
                    code="invalid_metadata_package",
                    detail=f"'{name}' is not valid YAML: {exc}",
                ) from exc

        for name, content in files:
            (pkg_dir / name).write_text(content, encoding="utf-8")
        logger.info("Updated metadata-package for model %s by %s", model_id, principal.subject)

        # Parse the updated package and sync every YAML-derived field into the DB.
        try:
            parsed = build_resource_from_package(pkg_dir)
        except (KeyError, TypeError, ValueError, FileNotFoundError, yaml.YAMLError) as exc:
            raise APIError(
                status_code=400,
                code="invalid_metadata_package",
                detail=f"Metadata-package saved but could not be parsed for model {model_id}: {exc}",  # noqa: E501
            ) from exc

        try:
            resource = self._registry.get_resource(model_id)
        except ResourceNotFoundError as exc:
            raise APIError(status_code=404, code="not_found", detail=str(exc)) from exc

        # Apply YAML-derived fields. Preserve system-managed fields:
        # id, owner, registration_status, metadata dict, location_uri (iRODS path),
        # execution_ref, format_tags, digest_sha256, size_bytes, io_spec, version_status,
        # new_version_of, superseded_by, organization, contact_email, date_published.
        resource.name = parsed.name
        resource.short_description = parsed.short_description
        resource.description = parsed.description
        # resource.version = parsed.version
        resource.external_ids = parsed.external_ids
        resource.license = parsed.license
        resource.authors = parsed.authors
        resource.contacts = parsed.contacts
        resource.publications = parsed.publications
        resource.related_resources = parsed.related_resources
        resource.funding = parsed.funding
        resource.model_scales = parsed.model_scales
        resource.organisms = parsed.organisms
        resource.domains = parsed.domains
        resource.infectious_agents = parsed.infectious_agents
        resource.health_conditions = parsed.health_conditions
        resource.biological_processes = parsed.biological_processes
        resource.molecular_entities = parsed.molecular_entities
        resource.proteins_genes = parsed.proteins_genes
        resource.model_class = parsed.model_class
        resource.formalism = parsed.formalism
        resource.determinism = parsed.determinism
        resource.time_dynamics = parsed.time_dynamics
        resource.spatial = parsed.spatial
        resource.multiscale = parsed.multiscale
        resource.execution_type = parsed.execution_type
        resource.execution_status = parsed.execution_status
        resource.language_name = parsed.language_name
        resource.language_version = parsed.language_version
        resource.execution_notes = parsed.execution_notes
        resource.dependencies = parsed.dependencies
        resource.containers = parsed.containers
        resource.compute = parsed.compute
        resource.entry_points = parsed.entry_points
        resource.tests = parsed.tests
        resource.io = parsed.io
        resource.registration_status = ResourceRegistrationStatus.APPROVED

        try:
            self._registry.update_resource(resource)
            self._session.commit()
        except RegistryValidationError as exc:
            self._session.rollback()
            raise APIError(status_code=400, code="validation_error", detail=str(exc)) from exc

        logger.info("Synced metadata-package to database for model %s", model_id)

        return [(name, (pkg_dir / name).read_text(encoding="utf-8")) for name in _PACKAGE_FILES]

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

    def find_user_runs(
        self,
        *,
        triggered_by: str,
        status: RunStatus | None = None,
    ) -> list[Run]:
        """All runs triggered by a user, across every model, optionally by status."""
        runs = self._registry.find_runs(status=status)
        return [run for run in runs if run.triggered_by == triggered_by]

    def find_user_run_details(
        self,
        *,
        triggered_by: str,
        status: RunStatus | None = None,
    ) -> list[tuple[Resource, Run, list[Resource], list[Resource]]]:
        """User's runs across every model, each hydrated with its model + I/O.

        Returns tuples of ``(model, run, input_resources, output_resources)``
        sorted newest-first by ``run.created_at``. This is a cross-model list,
        so every row carries its own model summary.

        Resource lookups (models and I/O) are cached by id within the call to
        avoid redundant ``get_resource`` round-trips when runs share inputs or
        target the same model. Missing resources are skipped gracefully rather
        than failing the whole list — a run may reference a resource (or model)
        that has since been deleted. No Execution-service refresh happens here;
        the UI refreshes active runs when a row is expanded.
        """
        runs = self.find_user_runs(triggered_by=triggered_by, status=status)
        runs.sort(key=lambda run: run.created_at, reverse=True)

        cache: dict[str, Resource] = {}

        def _resolve(rid: str) -> Resource | None:
            if rid in cache:
                return cache[rid]
            try:
                resource = self._registry.get_resource(rid)
            except ResourceNotFoundError:
                logger.warning("Run references missing resource %s", rid)
                return None
            cache[rid] = resource
            return resource

        details: list[tuple[Resource, Run, list[Resource], list[Resource]]] = []
        for run in runs:
            model = _resolve(run.model_id)
            if model is None:
                # A run whose model no longer exists can't be rendered as a row.
                logger.warning("Run %s references missing model %s", run.id, run.model_id)
                continue
            inputs = [r for rid in run.input_resource_ids if (r := _resolve(rid)) is not None]
            outputs = [r for rid in run.output_resource_ids if (r := _resolve(rid)) is not None]
            details.append((model, run, inputs, outputs))

        return details

    # ── Query operations ─────────────────────────────────────────────

    def list_models(
        self,
        *,
        name_contains: str | None = None,
        owner: str | None = None,
        tags: list[str] | None = None,
        organisms: list[str] | None = None,
        scales: list[str] | None = None,
        registration_status: str | None = None,
    ) -> list[Resource]:
        # FUTURE: batch fga check for visibility filtering
        resources = find_resources(
            self._registry,
            resource_type=ResourceType.MODEL,
            name_contains=name_contains,
            owner=owner,
            tags=tags,
            organisms=organisms,
            scales=scales,
        )
        if registration_status is not None:
            resources = [r for r in resources if r.registration_status.value == registration_status]
        return resources

    # ── Search ────────────────────────────────────────────────────────

    # Search only surfaces published resources: the active version of a resource
    # whose registration workflow reached APPROVED. Enforced here (not the
    # endpoint) so no caller can bypass or widen the gate.
    _SEARCH_GATE = {"version_status": "active", "registration_status": "approved"}

    def search(self, query: SearchQuery) -> SearchResult:
        """Validate and execute a full-text search with filters and aggregations.

        A fixed gate (version_status=active, registration_status=approved) is
        forced on every search, overriding any client-supplied filters on those
        fields so drafts / pending / rejected resources never leak into results.
        """
        # Drop client filters on the gated fields, then append the forced gate.
        kept = tuple(f for f in query.filters if f.field not in self._SEARCH_GATE)
        gate = tuple(FieldFilter(field=k, op="eq", value=v) for k, v in self._SEARCH_GATE.items())
        query = dataclasses.replace(query, filters=kept + gate)

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
        model_scales: list[str] | None = None,
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
                model_scales=model_scales or [],
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
        model_scales: list[str] | None = None,
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
        if model_scales is not None:
            resource.model_scales = model_scales
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

        if principal.issuer != "local" and resource.owner != principal.subject:
            raise self._not_authorized_error()
        return resource

    def mark_upload_complete(
        self,
        principal: AuthenticatedPrincipal,
        *,
        resource_id: str,
    ) -> Resource:
        """
        Stamp `metadata['upload_status'] = 'UPLOAD_COMPLETE'` on a resource owned by `principal`
        and reconcile its `location_uri` to where the upload actually landed.

        Why reconcile `location_uri` here? At create time the user supplies an
        arbitrary (iRODS or path) `location_uri`, but tus always writes to a
        deterministic path (`<resource_id>/<version>`, see `upload_dir`). If the two
        disagree, the download endpoint (which reads `location_uri`) cannot
        find the just-uploaded files. Stamping the canonical iRODS URI here —
        in the same atomic update as `upload_status` — keeps the two in sync
        without forcing the user to compute the path correctly at create time.

        Idempotent. `upload_status` is kept in `metadata` because
        `mism_registry.ResourceVersionStatus` models publication lifecycle
        (active/superseded/archived), not content lifecycle.
        """
        resource = self.get_resource_and_assert_ownership(principal, resource_id=resource_id)

        new_metadata = dict(resource.metadata)
        new_metadata["upload_status"] = "UPLOAD_COMPLETE"
        resource.metadata = new_metadata

        # Reconcile location_uri with the actual storage path tusd wrote to.
        # `upload_dir` is the single source of truth for the upload destination
        # (<resource_id>/<version>) and is also used by the tus pre-create hook.
        # Stored as a bare mount-relative path; resolve_location_uri joins it
        # onto IRODS_MOUNT_PATH (it strips any irods:// scheme anyway).
        resource.location_uri = upload_dir(resource_id, resource.version)

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

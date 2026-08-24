import dataclasses
import logging
import shutil
import time
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from mism_registry import (
    InvalidStateTransitionError,
    ResourceNotFoundError,
    ResourceType,
    RunStatus,
    find_resources,
    get_model_run_details,
    prepare_run,
    register_dataset,
    register_model,
    set_image_review_status,
    set_registration_status,
    submit_container_image,
)
from mism_registry import (
    ValidationError as RegistryValidationError,
)
from mism_registry.backends.postgres import PostgresRegistry
from mism_registry.enums import ExecutionType, ImageReviewStatus, ResourceRegistrationStatus
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
from mism_registry.types import Author, Container, IOSpec, Publication
from sqlalchemy.orm import Session

from mismapi.auth.principal import AuthenticatedPrincipal
from mismapi.clients.openfga_client import OpenFGAClient
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

#: Platform-wide singleton object every model's `platform` relation points at
#: (MISM-291). Lets any `platform:main#executor` holder execute any model via
#: `model#can_execute`'s tupleToUserset, without a per-model grant.
_PLATFORM_OBJECT = "platform:main"

#: The four platform-wide roles `GET /auth/capabilities` reports (MISM-291).
#: Kept in sync by hand with `mismapi.cli.manage_openfga_roles.VALID_ROLES`
#: and the OpenFGA schema — see Docs/OpenFGA/MISM-OpenFGA-Auth-Model.md.
#: Deliberately excludes `can_execute`: that's a per-model *derived* relation
#: (owner OR `executor`, via `model#platform`'s tupleToUserset), not a role a
#: principal directly holds the way the four below are.
_PLATFORM_ROLES: tuple[str, ...] = ("uploader", "upload_reviewer", "image_checker", "executor")


class RegistryService:
    """Orchestrates registry operations, session management, and (future) authz."""

    def __init__(
        self,
        registry: Registry,
        session: Session,
        openfga_client: OpenFGAClient | None = None,
    ) -> None:
        self._registry = registry
        self._session = session
        self._openfga_client = openfga_client

    def _openfga_client_for(self, principal: AuthenticatedPrincipal) -> OpenFGAClient | None:
        """The configured OpenFGA client, or None if OpenFGA calls should be
        skipped for this request.

        None when no client is configured (e.g. tests constructing
        RegistryService directly), or when ``issuer == "local"`` — set on
        every request when ``settings.disable_auth`` is True (see
        ``auth/base.py``'s ``require_principal``), matching the bypass
        ``get_resource_and_assert_ownership`` already uses for ownership
        checks. Local dev commonly runs without an OpenFGA instance at all
        (see `docker-compose.test.yaml`), so *every* OpenFGA interaction —
        role checks and tuple writes alike — is skipped in that mode, not
        just the check, otherwise a tuple write would fail with a real
        network error and reject the request anyway.
        """
        if self._openfga_client is None or principal.issuer == "local":
            return None
        return self._openfga_client

    async def _assert_uploader(self, principal: AuthenticatedPrincipal) -> None:
        """Gate resource creation on the platform-wide `uploader` role (MISM-291)."""
        client = self._openfga_client_for(principal)
        if client is None:
            return
        allowed = await client.check(
            user=f"user:{principal.subject}", relation="uploader", object_=_PLATFORM_OBJECT
        )
        if not allowed:
            raise APIError(
                status_code=403,
                code="not_authorized",
                detail="Principal does not hold the platform uploader role.",
            )

    async def _assert_upload_reviewer(self, principal: AuthenticatedPrincipal) -> None:
        """Gate metadata-review actions on the platform-wide `upload_reviewer` role
        (MISM-291).

        Global, not per-submission (see
        ``Docs/OpenFGA/MISM-OpenFGA-Auth-Model.md``'s open question #11): any
        holder of this role may review any ``PENDING_REVIEW`` model, including
        one they uploaded themselves — self-review is explicitly allowed, so
        this does not compare ``principal.subject`` against ``resource.owner``.
        """
        client = self._openfga_client_for(principal)
        if client is None:
            return
        allowed = await client.check(
            user=f"user:{principal.subject}",
            relation="upload_reviewer",
            object_=_PLATFORM_OBJECT,
        )
        if not allowed:
            raise APIError(
                status_code=403,
                code="not_authorized",
                detail="Principal does not hold the platform upload_reviewer role.",
            )

    async def _assert_image_checker(self, principal: AuthenticatedPrincipal) -> None:
        """Gate Dockerfile/image-review actions on the platform-wide `image_checker`
        role (MISM-291, workflow steps i-k).

        Global, not per-submission, mirroring `_assert_upload_reviewer` exactly.
        Self-review is explicitly allowed (decided for this role, not carried over
        by assumption from `upload_reviewer`'s precedent): any holder of this role
        may vet any model's image, including one they themselves uploaded, so this
        does not compare `principal.subject` against `resource.owner`.
        """
        client = self._openfga_client_for(principal)
        if client is None:
            return
        allowed = await client.check(
            user=f"user:{principal.subject}",
            relation="image_checker",
            object_=_PLATFORM_OBJECT,
        )
        if not allowed:
            raise APIError(
                status_code=403,
                code="not_authorized",
                detail="Principal does not hold the platform image_checker role.",
            )

    async def _assert_can_execute(self, principal: AuthenticatedPrincipal, model_id: str) -> None:
        """Gate execution on the per-model `can_execute` relation (MISM-291,
        workflow steps g/n).

        Unlike the three platform-role gates above (which check a fixed
        `platform:main` object), `can_execute` is checked against the specific
        `model:{model_id}` object — it's a union of `owner` OR
        `platform#executor` via `model#platform`'s `tupleToUserset` (Phase 2's
        `create_model` writes both the `owner` and `platform` tuples needed for
        this to resolve). Same `_openfga_client_for` skip rules as the other
        gates (no client configured, or `issuer == "local"`).
        """
        client = self._openfga_client_for(principal)
        if client is None:
            return
        allowed = await client.check(
            user=f"user:{principal.subject}",
            relation="can_execute",
            object_=f"model:{model_id}",
        )
        if not allowed:
            raise APIError(
                status_code=403,
                code="not_authorized",
                detail="Principal is not authorized to execute this model.",
            )

    async def get_platform_capabilities(self, principal: AuthenticatedPrincipal) -> dict[str, bool]:
        """Report which platform-wide OpenFGA roles `principal` holds (MISM-291).

        Powers `GET /auth/capabilities`, giving the UI a single place to check
        role membership up front instead of guessing from `/auth/me` or
        403-probing individual endpoints. Checks each of `_PLATFORM_ROLES`
        against the same singleton `platform:main` object the
        `_assert_uploader`/`_assert_upload_reviewer`/`_assert_image_checker`
        gates check (`executor` here mirrors `_assert_can_execute`'s
        `platform:main#executor` half only — see `_PLATFORM_ROLES`'s docstring
        for why `can_execute` itself isn't one of the four).

        Deliberately asymmetric with `_openfga_client_for`'s combined skip
        rule for one of its two conditions: `issuer == "local"` still means
        "treat as fully permitted" (all four True), matching every
        `_assert_*` gate's dev-mode bypass — but an *unconfigured* OpenFGA
        client reports all four False here, not True. `_assert_*` treats a
        missing client as permissive so local dev without a running OpenFGA
        instance doesn't block resource creation; this is a read-only status
        endpoint whose entire purpose is telling the UI what's true, so
        reporting "yes" for a check that was never actually performed would
        be actively misleading rather than merely permissive.

        Four sequential `check` calls, not one batched request —
        `OpenFGAClient` doesn't currently expose a batch-check call (its
        `/check` wrapper is single-tuple only). Adding one was out of scope
        for a single new endpoint; worth revisiting if a second caller ever
        needs the same four-relation fan-out.
        """
        if self._openfga_client is None:
            return dict.fromkeys(_PLATFORM_ROLES, False)
        if principal.issuer == "local":
            return dict.fromkeys(_PLATFORM_ROLES, True)
        client = self._openfga_client
        user = f"user:{principal.subject}"
        return {
            role: await client.check(user=user, relation=role, object_=_PLATFORM_OBJECT)
            for role in _PLATFORM_ROLES
        }

    def _assert_input_resource_visible(
        self, principal: AuthenticatedPrincipal, resource: Resource
    ) -> None:
        """Reject naming a run input the caller may not view (MISM-291 Phase 5).

        Closes the gap flagged in ``Docs/OpenFGA/MISM-OpenFGA-Auth-Model.md``
        (goal 1, checklist item 8): ``create_run`` previously passed
        ``input_resource_ids`` straight to ``prepare_run`` with no visibility
        check, so a caller could name someone else's private dataset (or
        model — ``prepare_run`` places no type restriction on inputs) as a run
        input and have its contents surfaced back via the run's mounted
        filesystem/outputs.

        Interim string-equality check (not OpenFGA), matching this phase's
        decision to reuse existing visibility logic rather than build a real
        `can_view` check now — a real check would need the deferred
        `viewer@user:*` wildcard tuple-writing (goal 1) as a prerequisite, or
        it would incorrectly deny access to public/approved resources today.

        Same predicate as `_authz.py`'s `model_visible_to` (registration_status
        public, or owner match), duplicated here rather than imported: no
        `services` module imports from `api` anywhere in this codebase, and
        `get_resource_and_assert_ownership` below already establishes the
        precedent of a service-layer resource-access gate that duplicates
        `_authz.py`'s pattern rather than reaching into it. Raises 404 (not
        403), matching `_authz.py`'s id-oracle-avoidance convention for
        *visibility* checks specifically — as opposed to
        `get_resource_and_assert_ownership`'s 403, which gates
        mutation-ownership, a different question. Label is generic ("Resource"),
        not "Model" or "Dataset", since an input can be either.
        """
        public = resource.registration_status == ResourceRegistrationStatus.APPROVED
        owned_by_caller = bool(resource.owner) and resource.owner == principal.subject
        if not (public or owned_by_caller):
            raise APIError(
                status_code=404,
                code="not_found",
                detail=f"Resource '{resource.id}' not found.",
            )

    # ── Model operations ─────────────────────────────────────────────

    async def create_model(
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
        await self._assert_uploader(principal)
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
            # MISM-291: grant ownership + the platform boilerplate tuple so
            # model#can_execute's tupleToUserset (owner OR platform executor)
            # can resolve. Skipped per _openfga_client_for's rules (no client
            # configured, or local/disable_auth dev mode).
            client = self._openfga_client_for(principal)
            if client is not None:
                model_object = f"model:{resource.id}"
                await client.write_tuple(
                    user=f"user:{principal.subject}", relation="owner", object_=model_object
                )
                await client.write_tuple(
                    user=_PLATFORM_OBJECT, relation="platform", object_=model_object
                )
            self._session.commit()
        except RegistryValidationError as exc:
            self._session.rollback()
            raise APIError(status_code=400, code="validation_error", detail=str(exc)) from exc
        except APIError:
            self._session.rollback()
            raise

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

        self._registry.delete_resource(model_id)
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

        # Ownership check (goal 1 stopgap — string equality, not yet OpenFGA).
        # Missing model still 404s (checked above) before this; only an
        # existing-but-not-owned model reaches this 403. Mirrors
        # `get_resource_and_assert_ownership`'s `issuer == "local"` bypass so
        # local dev with auth disabled isn't blocked from updating models.
        #
        # FUTURE: fga.check(user=principal.subject,
        #   relation="editor", object=f"model:{model_id}")
        if principal.issuer != "local" and resource.owner != principal.subject:
            raise self._not_authorized_error()

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

    async def create_run(
        self,
        principal: AuthenticatedPrincipal,
        *,
        model_id: str,
        input_resource_ids: list[str] | None = None,
        entrypoint_index: int | None = None,
        arguments: dict[str, Any] | None = None,
        triggered_by: str = "",
        notes: str = "",
    ) -> Run:
        # Fetched (and its absence mapped to 404) before the OpenFGA check so a
        # bad model_id still 404s, matching this method's pre-existing behavior,
        # rather than surfacing as a 403 that reveals nothing was checked yet.
        try:
            self._registry.get_resource(model_id)
        except ResourceNotFoundError as exc:
            raise APIError(status_code=404, code="not_found", detail=str(exc)) from exc

        await self._assert_can_execute(principal, model_id)

        # MISM-291 Phase 5: each input must be visible to the caller before it
        # gets mounted into the run (goal 1's create_run gap). Fetched (and
        # 404-mapped) the same way as model_id above — prepare_run re-fetches
        # each one too, an accepted minor duplicate read, same tradeoff as the
        # model_id check above.
        for input_resource_id in input_resource_ids or []:
            try:
                input_resource = self._registry.get_resource(input_resource_id)
            except ResourceNotFoundError as exc:
                raise APIError(status_code=404, code="not_found", detail=str(exc)) from exc
            self._assert_input_resource_visible(principal, input_resource)

        try:
            run = prepare_run(
                self._registry,
                model_id=model_id,
                input_resource_ids=input_resource_ids or [],
                entrypoint_index=entrypoint_index,
                arguments=arguments or {},
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

    def find_resource_directory(self, resource_id: str) -> tuple[Resource, Path | None]:
        """Like ``get_resource_directory``, but yields ``None`` for a directory
        that isn't on the mount yet instead of raising 404.

        For *listing*, "this resource has no files on disk" is an empty result,
        not a failure — a registered model that was never uploaded, or whose
        upload is still pending, legitimately has nothing to list. Raising 404
        there forces every client to treat emptiness as an error, which is what
        stopped the detail page's Files section from server-rendering: the query
        errored, so `dehydrate()` dropped it and the browser refetched.

        Download keeps using the strict variant — there a missing directory
        really is a 404.
        """
        try:
            resource = self._registry.get_resource(resource_id)
        except ResourceNotFoundError as exc:
            raise APIError(status_code=404, code="not_found", detail=str(exc)) from exc

        mount = get_settings().irods_mount_path
        directory = resolve_location_uri(resource.location_uri, mount, missing_ok=True)
        if not directory.exists():
            return resource, None
        if not directory.is_dir():
            raise APIError(
                status_code=400,
                code="not_a_directory",
                detail=f"Resource location is not a directory: {resource.location_uri}",
            )
        return resource, directory

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

        The annotation job pod and this API pod mount the same iRODS PVC from
        different pods, so there's a brief window right after the annotation
        job is marked "succeeded" where the just-written package/files aren't
        yet visible through this pod's mount. Retry the existence check a
        bounded number of times before giving up, to absorb that propagation
        lag (settings.metadata_package_retry_max_attempts / _backoff_seconds).
        """
        try:
            model = self._registry.get_resource(model_id)
        except ResourceNotFoundError as exc:
            raise APIError(status_code=404, code="not_found", detail=str(exc)) from exc

        mount = get_settings().irods_mount_path
        # resolve_location_uri enforces the traversal check and that the dir exists.
        model_dir = resolve_location_uri(model.location_uri, mount)
        pkg_dir = model_dir / "metadata-package"

        settings = get_settings()
        max_attempts = settings.metadata_package_retry_max_attempts
        backoff_seconds = settings.metadata_package_retry_backoff_seconds
        missing: list[str] = []
        for attempt in range(1, max_attempts + 1):
            if not pkg_dir.is_dir():
                missing = ["metadata-package/"]
            else:
                missing = [
                    f for f in (METADATA_FILE, EXECUTION_FILE) if not (pkg_dir / f).is_file()
                ]
            if not missing:
                return pkg_dir
            if attempt < max_attempts:
                logger.warning(
                    "metadata_package_not_ready model_id=%s attempt=%s missing=%s",
                    model_id,
                    attempt,
                    missing,
                )
                time.sleep(backoff_seconds * attempt)

        if missing == ["metadata-package/"]:
            raise APIError(
                status_code=404,
                code="metadata_package_not_found",
                detail=f"No metadata-package directory found for model {model_id}.",
            )
        raise APIError(
            status_code=404,
            code="metadata_package_not_found",
            detail=f"metadata-package for model {model_id} is missing {', '.join(missing)}.",
        )

    def parse_metadata_package(self, model_id: str) -> tuple[Resource, list[str]]:
        """Parse the metadata-package for a model into a (transient) Resource.

        Reads ``metadata.yaml`` + ``execution.yaml`` and maps them onto a
        Resource. The result is *not* persisted — it's a preview of what the
        annotation package contains. Returns ``(resource, warnings)``:
        missing/empty required fields on individual entries (an author with
        no name, etc.) are tolerated by ``build_resource_from_package`` and
        reported here as non-blocking warnings rather than failing.

        Raises 404 (model / package / file missing) and 400 only if the
        file's basic structure is unreadable (malformed YAML, or the
        top-level ``model``/``execution`` section itself is absent).
        """
        pkg_dir = self._metadata_package_dir(model_id)
        try:
            return build_resource_from_package(pkg_dir)
        except (
            KeyError,
            TypeError,
            ValueError,
            AttributeError,
            FileNotFoundError,
            yaml.YAMLError,
        ) as exc:
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
    ) -> tuple[list[tuple[str, str]], list[str]]:
        """Write edited raw YAML back to the metadata-package, then re-read it.

        Only the two known filenames are accepted (blocks path traversal), and
        each file must parse as YAML before anything is written (all-or-nothing).
        Returns ``(files, warnings)`` — the re-read raw files plus any
        non-blocking issues found while parsing them into a Resource.

        The metadata-package is generated by an external annotator and may
        legitimately be missing data on individual entries the annotator
        couldn't confidently extract (e.g. an author with no name); those are
        tolerated by ``build_resource_from_package`` itself and reported here
        as non-blocking warnings rather than failing.

        This no longer decides approval (MISM-291) — that's
        ``review_metadata_package``'s job. If the package fails to parse at
        all — the top-level ``model``/``execution`` structure itself is
        broken — that is raised as an error, not downgraded to a warning: the
        DB is left untouched. The edited YAML text has already been written
        to disk by this point (validated above as syntactically-valid YAML),
        so the user's edits aren't lost; they can fix the structural issue
        and re-submit. On success, ``registration_status`` is left alone,
        with one exception: resubmitting a manually-fixed ``REJECTED``
        package moves it back to ``PENDING_REVIEW`` (the state machine's
        "resubmit after manual fix" transition) and clears
        ``metadata_rejection_reason``, so it re-enters the reviewer queue.

        Raises 403 (not owner), 404 (missing model/resource), 400 (unknown
        filename, syntactically malformed YAML, or a metadata-package that
        can't be mapped onto a Resource at all).
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
        # A structural parse failure means the package can't be trusted at all —
        # raise rather than approve, so the caller has to fix it and re-submit.
        try:
            parsed, warnings = build_resource_from_package(pkg_dir)
        except (
            KeyError,
            TypeError,
            ValueError,
            AttributeError,
            FileNotFoundError,
            yaml.YAMLError,
        ) as exc:
            raise APIError(
                status_code=400,
                code="invalid_metadata_package",
                detail=f"Metadata-package for model {model_id} could not be parsed: {exc}",
            ) from exc

        try:
            resource = self._registry.get_resource(model_id)
        except ResourceNotFoundError as exc:
            raise APIError(status_code=404, code="not_found", detail=str(exc)) from exc

        # Apply YAML-derived fields. Always preserve system-managed fields
        # regardless: id, owner, registration_status, metadata dict,
        # location_uri (iRODS path), execution_ref, format_tags, digest_sha256,
        # size_bytes, io_spec, version_status, new_version_of, superseded_by,
        # organization, contact_email, date_published.
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

        # Resubmitting a manually-fixed rejected package re-enters the
        # reviewer queue automatically — the state machine already allows
        # REJECTED -> PENDING_REVIEW for exactly this "resubmit after manual
        # fix" case. Every other status (PENDING_REVIEW, APPROVED,
        # DRAFT/ANNOTATING/ANNOTATION_FAILED — the latter three unreachable
        # here in practice since _metadata_package_dir 404s before a package
        # exists) is left untouched: this endpoint no longer decides
        # approval at all — see RegistryService.review_metadata_package.
        if resource.registration_status == ResourceRegistrationStatus.REJECTED:
            resource.registration_status = ResourceRegistrationStatus.PENDING_REVIEW
            resource.metadata_rejection_reason = ""

        try:
            self._registry.update_resource(resource)
            self._session.commit()
        except RegistryValidationError as exc:
            self._session.rollback()
            raise APIError(status_code=400, code="validation_error", detail=str(exc)) from exc

        logger.info("Synced metadata-package to database for model %s", model_id)

        files_out = [
            (name, (pkg_dir / name).read_text(encoding="utf-8")) for name in _PACKAGE_FILES
        ]
        return files_out, warnings

    async def review_metadata_package(
        self,
        principal: AuthenticatedPrincipal,
        *,
        model_id: str,
        approve: bool,
        reason: str = "",
    ) -> Resource:
        """An UPLOAD_REVIEWER's approve/reject decision on a model's metadata
        review (MISM-291, workflow steps e/f).

        Gated on the platform-wide ``upload_reviewer`` role — global, not
        per-submission, and self-review is explicitly allowed (a reviewer may
        act on a model they themselves uploaded). Delegates the actual
        ``PENDING_REVIEW -> APPROVED/REJECTED`` transition to
        ``mism_registry.set_registration_status``, which enforces the
        registration state machine and stamps ``metadata_reviewed_by``/
        ``metadata_reviewed_at``/``metadata_rejection_reason``.

        Raises 403 (not a reviewer), 404 (model missing), 400 (illegal
        transition, e.g. reviewing a model that isn't PENDING_REVIEW).
        """
        await self._assert_upload_reviewer(principal)

        target = (
            ResourceRegistrationStatus.APPROVED if approve else ResourceRegistrationStatus.REJECTED
        )
        try:
            resource = set_registration_status(
                self._registry,
                resource_id=model_id,
                target=target,
                reviewed_by=principal.subject,
                reason=reason,
            )
            self._session.commit()
        except ResourceNotFoundError as exc:
            self._session.rollback()
            raise APIError(status_code=404, code="not_found", detail=str(exc)) from exc
        except InvalidStateTransitionError as exc:
            self._session.rollback()
            raise APIError(
                status_code=400, code="invalid_state_transition", detail=str(exc)
            ) from exc

        logger.info(
            "Metadata review for model %s: %s by %s",
            model_id,
            target.value,
            principal.subject,
        )
        return resource

    def submit_container_image(
        self,
        principal: AuthenticatedPrincipal,
        *,
        model_id: str,
        container: Container,
    ) -> Resource:
        """Submit (or resubmit) a built Dockerfile/image for IMAGE_CHECK review
        (MISM-291, workflow steps h/l).

        Ownership-gated, not `image_checker`-gated — the design doc names no
        gating role for this step (only the review action itself, steps i-k,
        is role-gated), mirroring `write_metadata_package_raw`'s ownership
        gate rather than `review_metadata_package`'s role gate. Delegates to
        `mism_registry.submit_container_image`, which requires the model's
        metadata registration to already be APPROVED and moves
        `image_review_status` to `PENDING_IMAGE_CHECK`, replacing any
        existing container recipe.

        This same call is also the resubmission action after a rejection:
        calling it again while `image_review_status` is `IMAGE_REJECTED`
        auto-transitions back to `PENDING_IMAGE_CHECK` — the state machine
        already allows that transition, and there is no separate "resubmit"
        endpoint, matching the metadata-review flow's
        `REJECTED -> PENDING_REVIEW` bounceback convention.

        Raises 403 (not owner), 404 (model missing), 400 (registration not
        yet APPROVED, or an illegal image-review transition, e.g.
        resubmitting while a review is already PENDING_IMAGE_CHECK).
        """
        self.get_resource_and_assert_ownership(principal, resource_id=model_id)

        try:
            resource = submit_container_image(
                self._registry,
                resource_id=model_id,
                container=container,
            )
            self._session.commit()
        except RegistryValidationError as exc:
            self._session.rollback()
            raise APIError(status_code=400, code="validation_error", detail=str(exc)) from exc
        except InvalidStateTransitionError as exc:
            self._session.rollback()
            raise APIError(
                status_code=400, code="invalid_state_transition", detail=str(exc)
            ) from exc

        logger.info(
            "Submitted container image for model %s (%s) by %s",
            model_id,
            container.image_name or container.file,
            principal.subject,
        )
        return resource

    async def review_container_image(
        self,
        principal: AuthenticatedPrincipal,
        *,
        model_id: str,
        approve: bool,
        reason: str = "",
    ) -> Resource:
        """An IMAGE_CHECK holder's approve/reject decision on a model's
        Dockerfile/image (MISM-291, workflow steps i-k).

        Gated on the platform-wide ``image_checker`` role — global, not
        per-submission, and self-review is explicitly allowed (an image
        checker may act on a model they themselves uploaded, decided
        2026-08-21 as its own per-role choice, not carried over from
        ``upload_reviewer``'s precedent). Delegates the actual
        ``PENDING_IMAGE_CHECK -> IMAGE_APPROVED/IMAGE_REJECTED`` transition to
        ``mism_registry.set_image_review_status``, which enforces the
        image-review state machine and stamps ``image_reviewed_by``/
        ``image_reviewed_at``/``image_rejection_reason``.

        Raises 403 (not an image checker), 404 (model missing), 400 (illegal
        transition, e.g. reviewing a model that isn't PENDING_IMAGE_CHECK).
        """
        await self._assert_image_checker(principal)

        target = ImageReviewStatus.IMAGE_APPROVED if approve else ImageReviewStatus.IMAGE_REJECTED
        try:
            resource = set_image_review_status(
                self._registry,
                resource_id=model_id,
                target=target,
                reviewed_by=principal.subject,
                reason=reason,
            )
            self._session.commit()
        except ResourceNotFoundError as exc:
            self._session.rollback()
            raise APIError(status_code=404, code="not_found", detail=str(exc)) from exc
        except InvalidStateTransitionError as exc:
            self._session.rollback()
            raise APIError(
                status_code=400, code="invalid_state_transition", detail=str(exc)
            ) from exc

        logger.info(
            "Image review for model %s: %s by %s",
            model_id,
            target.value,
            principal.subject,
        )
        return resource

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
        triggered_by: str | None = None,
    ) -> ModelRunSummary:
        """Return the model plus its runs with hydrated I/O resources.

        Used by the model detail page's run history. Pass ``triggered_by`` to
        scope the result to one user's runs.

        Preferred path pushes ``triggered_by`` into the query so other users'
        runs are never hydrated. That parameter only exists in the
        metadata-schema working tree, not in the DAL revision
        ``api/pyproject.toml`` pins, so there is a compatibility fallback that
        filters after the fact. The fallback is strictly less efficient — it
        hydrates rows it then discards — but it must never be less *safe*: both
        paths return only the caller's runs. Delete the fallback once the pinned
        DAL ref is bumped.
        """
        try:
            try:
                summary = get_model_run_details(  # type: ignore[call-arg]
                    self._registry,
                    model_id=model_id,
                    status=status,
                    triggered_by=triggered_by,
                )
            except TypeError:
                summary = get_model_run_details(self._registry, model_id=model_id, status=status)
                if triggered_by is not None:
                    summary = dataclasses.replace(
                        summary,
                        runs=[
                            detail
                            for detail in summary.runs
                            if detail.run.triggered_by == triggered_by
                        ],
                    )
            return summary
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
        return self._registry.find_runs(triggered_by=triggered_by, status=status)

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

    async def create_dataset(
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
        await self._assert_uploader(principal)
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

        # Ownership check (goal 1 stopgap — string equality, not yet OpenFGA).
        # Missing dataset still 404s (checked above) before this; only an
        # existing-but-not-owned dataset reaches this 403. Mirrors
        # `get_resource_and_assert_ownership`'s `issuer == "local"` bypass so
        # local dev with auth disabled isn't blocked from updating datasets.
        #
        # FUTURE: fga.check(user=principal.subject,
        #   relation="editor", object=f"dataset:{dataset_id}")
        if principal.issuer != "local" and resource.owner != principal.subject:
            raise self._not_authorized_error()

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

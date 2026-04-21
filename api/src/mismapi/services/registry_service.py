import logging
from typing import Any, cast

from mism_registry import (
    ResourceNotFoundError,
    ResourceType,
    prepare_run,
    register_dataset,
    register_model,
)
from mism_registry import (
    ValidationError as RegistryValidationError,
)
from mism_registry.backends.postgres import ResourceModel, resource_from_db
from mism_registry.enums import ExecutionType
from mism_registry.protocol import Registry
from mism_registry.resource import Resource
from mism_registry.run import Run
from mism_registry.search import (
    AGGREGATABLE_FIELDS,
    FILTERABLE_FIELDS,
    SearchQuery,
    SearchResult,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from mismapi.auth.principal import AuthenticatedPrincipal
from mismapi.core.errors import APIError

logger = logging.getLogger(__name__)


def _apply_resource_list_filters(
    stmt: Any,
    *,
    resource_type: ResourceType | None,
    tags: list[str] | None,
    owner: str | None,
    name_contains: str | None,
    organisms: list[str] | None,
    scales: list[str] | None,
) -> Any:
    """Mirror ``PostgresRegistry.find_resources`` WHERE clauses (same semantics)."""
    if resource_type is not None:
        stmt = stmt.where(ResourceModel.resource_type == resource_type)
    if tags is not None:
        stmt = stmt.where(ResourceModel.format_tags.contains(tags))
    if owner is not None:
        stmt = stmt.where(ResourceModel.owner == owner)
    if name_contains is not None:
        stmt = stmt.where(ResourceModel.name.ilike(f"%{name_contains}%"))
    if organisms is not None:
        stmt = stmt.where(ResourceModel.organisms.overlap(organisms))
    if scales is not None:
        stmt = stmt.where(ResourceModel.modeling_scales.overlap(scales))
    return stmt


def _fetch_resources_page(
    session: Session,
    *,
    resource_type: ResourceType | None,
    tags: list[str] | None,
    owner: str | None,
    name_contains: str | None,
    organisms: list[str] | None,
    scales: list[str] | None,
    limit: int,
    offset: int,
) -> list[Resource]:
    stmt = select(ResourceModel)
    stmt = _apply_resource_list_filters(
        stmt,
        resource_type=resource_type,
        tags=tags,
        owner=owner,
        name_contains=name_contains,
        organisms=organisms,
        scales=scales,
    )
    stmt = stmt.order_by(ResourceModel.created_at.desc()).limit(limit).offset(offset)
    rows = session.execute(stmt).scalars().all()
    return [resource_from_db(m) for m in rows]


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
        description: str = "",
        version: str = "",
        owner: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> Resource:
        try:
            resource = register_model(
                self._registry,
                name=name,
                location_uri=location_uri,
                execution_type=execution_type,
                description=description,
                version=version,
                owner=owner or principal.subject,
                metadata=metadata or {},
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
        metadata: dict[str, Any] | None = None,
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
        if metadata is not None:
            resource.metadata = metadata

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

    # ── Query operations ─────────────────────────────────────────────

    def list_models(
        self,
        *,
        name_contains: str | None = None,
        owner: str | None = None,
        tags: list[str] | None = None,
        organisms: list[str] | None = None,
        scales: list[str] | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> list[Resource]:
        # FUTURE: batch fga check for visibility filtering
        return _fetch_resources_page(
            self._session,
            resource_type=ResourceType.MODEL,
            name_contains=name_contains,
            owner=owner,
            tags=tags,
            organisms=organisms,
            scales=scales,
            limit=limit,
            offset=offset,
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

        search_resources = getattr(self._registry, "search_resources", None)
        if not callable(search_resources):
            raise APIError(
                status_code=501,
                code="unsupported_backend",
                detail="Full-text search is not supported by the configured registry backend",
            )

        return cast(SearchResult, search_resources(query))

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
        metadata: dict[str, Any] | None = None,
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
                metadata=metadata or {},
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
        metadata: dict[str, Any] | None = None,
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
        if metadata is not None:
            resource.metadata = metadata

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
        limit: int = 25,
        offset: int = 0,
    ) -> list[Resource]:
        # FUTURE: batch fga check for visibility filtering
        return _fetch_resources_page(
            self._session,
            resource_type=ResourceType.DATASET,
            name_contains=name_contains,
            owner=owner,
            tags=tags,
            organisms=organisms,
            scales=scales,
            limit=limit,
            offset=offset,
        )

    # ── Lifecycle ────────────────────────────────────────────────────

    def close(self) -> None:
        self._session.close()

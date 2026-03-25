import logging
from typing import Any

from sqlalchemy.orm import Session

from mism_registry import (
    ResourceNotFoundError,
    ResourceType,
    ValidationError as RegistryValidationError,
    find_resources,
    prepare_run,
    register_dataset,
    register_model,
)
from mism_registry.protocol import Registry
from mism_registry.resource import Resource
from mism_registry.run import Run
from mismapi.auth.base import AuthenticatedPrincipal
from mismapi.core.errors import APIError

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
        execution_type: str,
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
            # FUTURE: fga.write_tuple(user=principal.subject, relation="owner", object=f"model:{resource.id}")
            self._session.commit()
        except RegistryValidationError as exc:
            self._session.rollback()
            raise APIError(status_code=400, code="validation_error", detail=str(exc))

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
        execution_type: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Resource:
        try:
            resource = self._registry.get_resource(model_id)
        except ResourceNotFoundError as exc:
            raise APIError(status_code=404, code="not_found", detail=str(exc))

        # FUTURE: fga.check(user=principal.subject, relation="editor", object=f"model:{model_id}")

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
            raise APIError(status_code=400, code="validation_error", detail=str(exc))

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
            # FUTURE: fga.write_tuple(user=principal.subject, relation="owner", object=f"run:{run.id}")
            self._session.commit()
        except ResourceNotFoundError as exc:
            self._session.rollback()
            raise APIError(status_code=404, code="not_found", detail=str(exc))
        except RegistryValidationError as exc:
            self._session.rollback()
            raise APIError(status_code=400, code="validation_error", detail=str(exc))

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
            # FUTURE: fga.write_tuple(user=principal.subject, relation="owner", object=f"dataset:{resource.id}")
            self._session.commit()
        except RegistryValidationError as exc:
            self._session.rollback()
            raise APIError(status_code=400, code="validation_error", detail=str(exc))

        logger.info("Registered dataset %s (%s) by %s", resource.id, resource.name, principal.subject)
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
            raise APIError(status_code=404, code="not_found", detail=str(exc))

        # FUTURE: fga.check(user=principal.subject, relation="editor", object=f"dataset:{dataset_id}")

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
            raise APIError(status_code=400, code="validation_error", detail=str(exc))

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

    # ── Lifecycle ────────────────────────────────────────────────────

    def close(self) -> None:
        self._session.close()

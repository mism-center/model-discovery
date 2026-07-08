"""Shared mappers from registry dataclasses → API response schemas.

Lives separately from any single router so multiple routers (models.py,
runs.py, …) can build identical RunDetailItem / ResourceSummaryItem payloads.
"""

from mism_registry.resource import Resource
from mism_registry.run import Run

from mismapi.schemas.registry import (
    ResourceSummaryItem,
    RunDetailItem,
    author_to_dto,
    io_spec_to_dto,
    pub_to_dto,
)


def resource_summary(r: Resource) -> ResourceSummaryItem:
    """Map a Resource dataclass → ResourceSummaryItem response model."""
    return ResourceSummaryItem(
        id=r.id,
        name=r.name,
        resource_type=r.resource_type.value,
        location_uri=r.location_uri,
        description=r.description,
        version=r.version,
        status=r.version_status.value,
        owner=r.owner,
        format_tags=list(r.format_tags),
        authors=[author_to_dto(a) for a in r.authors],
        organization=r.organization,
        contact_email=r.contact_email,
        publications=[pub_to_dto(p) for p in r.publications],
        funding=list(r.funding),
        modeling_scales=list(r.model_scales),
        organisms=list(r.organisms),
        domains=list(r.domains),
        date_published=r.date_published,
        digest_sha256=r.digest_sha256,
        size_bytes=r.size_bytes,
        external_ids=dict(r.external_ids),
        license=r.license,
        execution_type=r.execution_type.value if r.execution_type else None,
        execution_ref=r.execution_ref,
        io_spec=io_spec_to_dto(r.io_spec) if r.io_spec else None,
        metadata=dict(r.metadata),
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


def run_detail(run: Run) -> RunDetailItem:
    """Map a Run dataclass → RunDetailItem response model."""
    return RunDetailItem(
        id=run.id,
        model_id=run.model_id,
        model_version=run.model_version,
        status=run.status.value,
        input_resource_ids=list(run.input_resource_ids),
        output_resource_ids=list(run.output_resource_ids),
        parameters=dict(run.parameters),
        started_at=run.started_at,
        completed_at=run.completed_at,
        error_message=run.error_message,
        log_uri=run.log_uri,
        triggered_by=run.triggered_by,
        notes=run.notes,
        created_at=run.created_at,
    )

import logging

from fastapi import APIRouter, Depends, Query
from mism_registry.enums import RunStatus
from mism_registry.resource import Resource
from mism_registry.run import Run

from mismapi.auth.base import AuthenticatedPrincipal, require_principal
from mismapi.clients.execution_client import ExecutionClient
from mismapi.dependencies.execution import get_execution_client
from mismapi.dependencies.registry import get_registry_service
from mismapi.schemas.registry import (
    CreateRunRequest,
    CreateRunResponse,
    ExecuteRunRequest,
    ExecuteRunResponse,
    ModelRunDetailItem,
    ModelRunDetailsResponse,
    RegisterModelRequest,
    RegisterModelResponse,
    ResourceSummaryItem,
    RunDetailItem,
    UpdateModelRequest,
)
from mismapi.schemas.search import ModelListItem, ModelListResponse
from mismapi.services.registry_service import RegistryService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/models", response_model=ModelListResponse)
async def list_models(
    name: str | None = Query(default=None, description="Substring match on model name"),
    owner: str | None = Query(default=None, description="Exact match on owner"),
    tags: list[str] | None = Query(default=None, description="Format tags (all must match)"),
    organisms: list[str] | None = Query(default=None, description="Organisms (any must match)"),
    scales: list[str] | None = Query(default=None, description="Modeling scales (any must match)"),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: RegistryService = Depends(get_registry_service),
) -> ModelListResponse:

    resources = service.list_models(
        name_contains=name,
        owner=owner,
        tags=tags,
        organisms=organisms,
        scales=scales,
    )

    total = len(resources)
    page = resources[offset : offset + limit]

    results = [
        ModelListItem(
            id=r.id,
            name=r.name,
            resource_type=r.resource_type.value,
            location_uri=r.location_uri,
            execution_type=r.execution_type.value if r.execution_type else None,
            version=r.version,
            status=r.status.value,
            owner=r.owner,
            description=r.description,
            created_at=r.created_at,
        )
        for r in page
    ]

    return ModelListResponse(total=total, results=results)


@router.post("/models", response_model=RegisterModelResponse, status_code=201)
async def create_model(
    payload: RegisterModelRequest,
    principal: AuthenticatedPrincipal = Depends(require_principal),
    service: RegistryService = Depends(get_registry_service),
) -> RegisterModelResponse:

    resource = service.create_model(
        principal,
        name=payload.name,
        location_uri=payload.location_uri,
        execution_type=payload.execution_type,
        description=payload.description,
        version=payload.version,
        owner=payload.owner,
        metadata=payload.metadata,
    )

    return RegisterModelResponse(
        id=resource.id,
        name=resource.name,
        resource_type=resource.resource_type.value,
        location_uri=resource.location_uri,
        execution_type=resource.execution_type.value if resource.execution_type else None,
        version=resource.version,
        status=resource.status.value,
        created_at=resource.created_at,
    )


@router.put("/models/{model_id}", response_model=RegisterModelResponse)
async def update_model(
    model_id: str,
    payload: UpdateModelRequest,
    principal: AuthenticatedPrincipal = Depends(require_principal),
    service: RegistryService = Depends(get_registry_service),
) -> RegisterModelResponse:

    resource = service.update_model(
        principal,
        model_id=model_id,
        name=payload.name,
        description=payload.description,
        version=payload.version,
        owner=payload.owner,
        location_uri=payload.location_uri,
        execution_type=payload.execution_type,
        metadata=payload.metadata,
    )

    return RegisterModelResponse(
        id=resource.id,
        name=resource.name,
        resource_type=resource.resource_type.value,
        location_uri=resource.location_uri,
        execution_type=resource.execution_type.value if resource.execution_type else None,
        version=resource.version,
        status=resource.status.value,
        created_at=resource.created_at,
    )


@router.post(
    "/models/{model_id}/runs",
    response_model=ExecuteRunResponse,
    status_code=201,
)
async def execute_run(
    model_id: str,
    payload: ExecuteRunRequest,
    principal: AuthenticatedPrincipal = Depends(require_principal),
    service: RegistryService = Depends(get_registry_service),
    execution_client: ExecutionClient = Depends(get_execution_client),
) -> ExecuteRunResponse:
    """Create a run and immediately trigger execution on the Execution API."""

    # 1. Register the run in the DAL (same as create_run)
    run = service.create_run(
        principal,
        model_id=model_id,
        input_resource_ids=payload.input_resource_ids,
        parameters=payload.parameters,
        triggered_by=payload.triggered_by,
        notes=payload.notes,
    )

    # 2. Forward to Execution API
    if payload.mode == "interactive":
        exec_response = await execution_client.launch_interactive(run.id)
    else:
        exec_response = await execution_client.launch_batch(run.id)

    logger.info(
        "Executed run %s for model %s (mode=%s) by %s",
        run.id,
        model_id,
        payload.mode,
        principal.subject,
    )

    return ExecuteRunResponse(
        id=run.id,
        model_id=run.model_id,
        model_version=run.model_version,
        status=run.status.value,
        input_resource_ids=list(run.input_resource_ids),
        created_at=run.created_at,
        execution=exec_response,
    )


# ── Helpers ──────────────────────────────────────────────────────


def _resource_summary(r: Resource) -> ResourceSummaryItem:
    return ResourceSummaryItem(
        id=r.id,
        name=r.name,
        resource_type=r.resource_type.value,
        location_uri=r.location_uri,
        description=r.description,
        version=r.version,
        status=r.status.value,
        owner=r.owner,
        format_tags=list(r.format_tags),
        created_at=r.created_at,
    )


def _run_detail(run: Run) -> RunDetailItem:
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


# ── GET /models/{model_id}/runs ─────────────────────────────────


@router.get("/models/{model_id}/runs", response_model=ModelRunDetailsResponse)
async def list_model_runs(
    model_id: str,
    status: RunStatus | None = Query(
        default=None, description="Optional filter — only include runs with this status."
    ),
    service: RegistryService = Depends(get_registry_service),
) -> ModelRunDetailsResponse:
    """Fetch all runs for a model, enriched with hydrated input/output resources.

    Designed to populate the UI's "Model Runs" page in a single call.
    """
    summary = service.get_model_run_details(model_id=model_id, status=status)

    runs = [
        ModelRunDetailItem(
            run=_run_detail(detail.run),
            input_resources=[_resource_summary(r) for r in detail.input_resources],
            output_resources=[_resource_summary(r) for r in detail.output_resources],
        )
        for detail in summary.runs
    ]

    return ModelRunDetailsResponse(
        model=_resource_summary(summary.model),
        runs=runs,
        total=len(runs),
    )

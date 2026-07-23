"""Run-scoped endpoints — orchestrate Discovery DAL + Execution service.

GET /runs/{run_id} hits the Execution API first so its lazy DAL refresh
fires, then reads the run back from the DAL with the freshly-updated status.
"""

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Query
from mism_registry import RunStatus
from pydantic import BaseModel

from mismapi.api.v1._run_helpers import resource_summary, run_detail
from mismapi.auth.base import AuthenticatedPrincipalDep
from mismapi.core.deps import ExecutionClientDep, RegistryServiceDep, SettingsDep
from mismapi.schemas.registry import RunDetailResponse, UserRunItem, UserRunsResponse


class AnnotateRunResponse(BaseModel):
    run_id: str
    execution_status: dict[str, Any] = {}


logger = logging.getLogger(__name__)

# Statuses a run can no longer move out of — no point polling the Execution
# service for these, and no risk of them going stale.
_TERMINAL_STATUSES = frozenset(
    {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED}
)

router = APIRouter()


@router.get("/me/runs", response_model=UserRunsResponse)
async def list_my_runs(
    service: RegistryServiceDep,
    execution_client: ExecutionClientDep,
    principal: AuthenticatedPrincipalDep,
    status: RunStatus | None = Query(
        default=None, description="Optional filter — only include runs with this status."
    ),
) -> UserRunsResponse:
    """List every run the calling user has triggered, across all models.

    Returns runs newest-first (by created_at), each hydrated with its model
    summary and input/output resources. Requires authentication (401 for
    anonymous callers).

    Non-terminal runs are reconciled with the Execution service first (same lazy
    refresh as ``GET /runs/{run_id}?refresh=true``) so a user's own history is
    always current — a run that finished won't linger as "running" until its row
    is opened. Terminal runs are skipped (their status can't change), and a
    failed status poll for one run is logged and ignored rather than failing the
    whole list.
    """
    # Read the run records first so we know which runs are still active and
    # worth a round-trip to the Execution service.
    active_run_ids = [
        run.id
        for run in service.find_user_runs(
            triggered_by=principal.subject, status=status
        )
        if run.status not in _TERMINAL_STATUSES
    ]

    if active_run_ids:
        # Trigger the Execution service's lazy DAL refresh for each active run,
        # concurrently. `return_exceptions=True` keeps one unreachable run from
        # sinking the whole history fetch.
        results = await asyncio.gather(
            *(execution_client.get_status(run_id) for run_id in active_run_ids),
            return_exceptions=True,
        )
        for run_id, result in zip(active_run_ids, results, strict=True):
            if isinstance(result, Exception):
                logger.warning(
                    "Failed to refresh status for run %s in history list: %s",
                    run_id,
                    result,
                )

    # Read back the (now-refreshed) run records, hydrated with model + I/O.
    details = service.find_user_run_details(
        triggered_by=principal.subject,
        status=status,
    )

    runs = [
        UserRunItem(
            model=resource_summary(model),
            run=run_detail(run),
            input_resources=[resource_summary(r) for r in inputs],
            output_resources=[resource_summary(r) for r in outputs],
        )
        for model, run, inputs, outputs in details
    ]

    return UserRunsResponse(runs=runs, total=len(runs))


@router.get("/runs/{run_id}", response_model=RunDetailResponse)
async def get_run(
    run_id: str,
    service: RegistryServiceDep,
    execution_client: ExecutionClientDep,
    refresh: bool = Query(
        default=True,
        description=(
            "When true (default), call the Execution service first so its lazy "
            "DAL refresh fires before we read the Run record — guaranteeing the "
            "freshest status. Set to false to skip the round-trip and return "
            "whatever the DAL has cached (cheap; useful for list-row previews)."
        ),
    ),
) -> RunDetailResponse:
    """Fetch a run by id, optionally refreshing status via the Execution service.

    Order matters when refresh=true:
      1. Call Execution API → it performs a lazy status check and writes the
         updated state into the DAL.
      2. Read the Run record from the DAL → now reflects the latest status.

    If the Execution call fails we surface the error to the caller; if it
    times out the client gets a 504 (see ExecutionClient.get_status).
    """
    execution_status: dict[str, Any] = {}
    if refresh:
        # 1. Trigger lazy refresh on the execution side.
        execution_status = await execution_client.get_status(run_id)

    # 2. Read the (now-fresh, if refreshed) Run record + hydrate referenced resources.
    run, input_resources, output_resources = service.get_run(run_id)

    return RunDetailResponse(
        run=run_detail(run),
        input_resources=[resource_summary(r) for r in input_resources],
        output_resources=[resource_summary(r) for r in output_resources],
        execution_status=execution_status,
    )


@router.post("/runs/{run_id}", response_model=AnnotateRunResponse, status_code=200)
async def post_run(
    run_id: str,
    execution_client: ExecutionClientDep,
    settings: SettingsDep,
) -> AnnotateRunResponse:
    """Submit an annotation job to the Execution service for the given resource.

    All job configuration (image, resources, prompt) comes from server-side
    settings. The LLM API key is injected by the execution-platform from its
    own environment — it is never passed through this request.
    """
    execution_status = await execution_client.annotate(
        resource_id=run_id,
        image=settings.annotation_job_image,
        prompt=settings.annotation_job_prompt,
        cpus=settings.annotation_job_cpus,
        memory=settings.annotation_job_memory,
        openai_base_url=settings.annotation_openai_base_url,
        model=settings.annotation_model,
    )
    return AnnotateRunResponse(run_id=run_id, execution_status=execution_status)


@router.delete("/runs/{run_id}", response_model=RunDetailResponse)
async def cancel_run(
    run_id: str,
    service: RegistryServiceDep,
    execution_client: ExecutionClientDep,
) -> RunDetailResponse:
    """Cancel a run by proxying DELETE to the Execution service.

    Order matters:
      1. Call Execution API DELETE → it stops the run and updates DAL status
         to CANCELLED.
      2. Read the now-updated Run record from the DAL → reflects the cancel.

    Returns the same shape as GET /runs/{run_id} so the UI can swap-in the
    response without a second round-trip.
    """
    # 1. Ask exec to actually cancel — it owns the running container/process.
    execution_status = await execution_client.cancel_run(run_id)

    # 2. Read the canceled Run record (and hydrate referenced resources).
    run, input_resources, output_resources = service.get_run(run_id)

    logger.info("Cancelled run %s (final status=%s)", run_id, run.status.value)

    return RunDetailResponse(
        run=run_detail(run),
        input_resources=[resource_summary(r) for r in input_resources],
        output_resources=[resource_summary(r) for r in output_resources],
        execution_status=execution_status,
    )

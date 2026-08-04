"""Run-scoped endpoints — orchestrate Discovery DAL + Execution service.

GET /runs/{run_id} hits the Execution API first so its lazy DAL refresh
fires, then reads the run back from the DAL with the freshly-updated status.
"""

import logging
from typing import Any

from fastapi import APIRouter, Query
from mism_registry import RunStatus
from pydantic import BaseModel

from mismapi.api.v1._authz import assert_resource_owner, assert_run_owner
from mismapi.api.v1._run_helpers import resource_summary, run_detail
from mismapi.auth.base import AuthenticatedPrincipalDep
from mismapi.core.deps import ExecutionClientDep, RegistryServiceDep, SettingsDep
from mismapi.schemas.registry import RunDetailResponse, UserRunItem, UserRunsResponse


class AnnotateResourceResponse(BaseModel):
    resource_id: str
    execution_status: dict[str, Any] = {}


logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/me/runs", response_model=UserRunsResponse)
async def list_my_runs(
    service: RegistryServiceDep,
    principal: AuthenticatedPrincipalDep,
    status: RunStatus | None = Query(
        default=None, description="Optional filter — only include runs with this status."
    ),
) -> UserRunsResponse:
    """List every run the calling user has triggered, across all models.

    Returns runs newest-first (by created_at), each hydrated with its model
    summary and input/output resources. Requires authentication (401 for
    anonymous callers). No Execution-service refresh is performed here — the UI
    refreshes active runs when a row is expanded.
    """
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
    principal: AuthenticatedPrincipalDep,
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

    Requires authentication, and only the user who triggered the run may read
    it (404 otherwise — see ``_authz``).
    """
    # Check ownership *before* the refresh round-trip: calling the Execution
    # service for someone else's run would fire a side effect on it and leak
    # its existence through timing and error shape.
    run, input_resources, output_resources = service.get_run(run_id)
    assert_run_owner(run, principal)

    execution_status: dict[str, Any] = {}
    if refresh:
        # 1. Trigger lazy refresh on the execution side.
        execution_status = await execution_client.get_status(run_id)
        # 2. Re-read so the record reflects the status Execution just wrote.
        run, input_resources, output_resources = service.get_run(run_id)

    return RunDetailResponse(
        run=run_detail(run),
        input_resources=[resource_summary(r) for r in input_resources],
        output_resources=[resource_summary(r) for r in output_resources],
        execution_status=execution_status,
    )


@router.post(
    "/resources/{resource_id}/annotate",
    response_model=AnnotateResourceResponse,
    status_code=200,
)
async def annotate_resource(
    resource_id: str,
    service: RegistryServiceDep,
    execution_client: ExecutionClientDep,
    settings: SettingsDep,
    principal: AuthenticatedPrincipalDep,
) -> AnnotateResourceResponse:
    """Submit an annotation job to the Execution service for a resource.

    All job configuration (image, resources, prompt) comes from server-side
    settings. The LLM API key is injected by the execution-platform from its
    own environment — it is never passed through this request.

    Requires authentication *and* ownership of the target resource. This endpoint
    spends the deployment's LLM budget, so it must be reachable neither
    anonymously nor by a signed-in user pointing it at someone else's resource.

    Was `POST /runs/{run_id}`, whose path param was forwarded to the Execution
    service as `resource_id` — so despite the name it never identified a run.
    That misnaming is what made the ownership rule look ambiguous and left the
    endpoint unguarded. The URL now matches the id space it actually takes, and
    sits alongside the other `/resources/{id}/...` routes. Safe to move: nothing
    called it — the UI uses only GET and DELETE `/runs/{run_id}`.
    """
    resource = service.get_model(resource_id)
    assert_resource_owner(resource, principal)

    logger.info("Annotation requested for %s by %s", resource_id, principal.subject)
    execution_status = await execution_client.annotate(
        resource_id=resource_id,
        image=settings.annotation_job_image,
        prompt=settings.annotation_job_prompt,
        cpus=settings.annotation_job_cpus,
        memory=settings.annotation_job_memory,
        openai_base_url=settings.annotation_openai_base_url,
        model=settings.annotation_model,
    )
    return AnnotateResourceResponse(resource_id=resource_id, execution_status=execution_status)


@router.delete("/runs/{run_id}", response_model=RunDetailResponse)
async def cancel_run(
    run_id: str,
    service: RegistryServiceDep,
    execution_client: ExecutionClientDep,
    principal: AuthenticatedPrincipalDep,
) -> RunDetailResponse:
    """Cancel a run by proxying DELETE to the Execution service.

    Order matters:
      0. Read the Run and verify the caller triggered it — this precedes the
         Execution call because cancelling is destructive and irreversible.
      1. Call Execution API DELETE → it stops the run and updates DAL status
         to CANCELLED.
      2. Read the now-updated Run record from the DAL → reflects the cancel.

    Returns the same shape as GET /runs/{run_id} so the UI can swap-in the
    response without a second round-trip.
    """
    # 0. Authorize before the side effect: only the triggering user may cancel.
    existing, _, _ = service.get_run(run_id)
    assert_run_owner(existing, principal)

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

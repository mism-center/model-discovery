"""Run-scoped endpoints — orchestrate Discovery DAL + Execution service.

GET /runs/{run_id} hits the Execution API first so its lazy DAL refresh
fires, then reads the run back from the DAL with the freshly-updated status.
"""

import logging
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from mismapi.api.v1._run_helpers import resource_summary, run_detail
from mismapi.auth.base import AuthenticatedPrincipalDep
from mismapi.core.deps import ExecutionClientDep, RegistryServiceDep, SettingsDep
from mismapi.schemas.registry import RunDetailResponse


class AnnotateRunResponse(BaseModel):
    run_id: str
    execution_status: dict[str, Any] = {}


logger = logging.getLogger(__name__)

router = APIRouter()


def _build_annotation_payload(
    model_id: str,
    username: str,
    settings: Any,
) -> dict[str, Any]:
    """Build the execution service job payload for a batch annotation run.

    All values come from server-side settings; nothing sensitive is passed
    from the browser.
    """
    return {
        "name": f"{model_id}-job",
        "identifier": model_id,
        "image": settings.annotation_job_image,
        "cpus": settings.annotation_job_cpus,
        "memory": settings.annotation_job_memory,
        "username": username,
        "version": "v1",
        "command": settings.annotation_job_command,
        "env": {
            "MODEL_INPUT": "/workspace/v1",
            "PROMPT": settings.annotation_job_prompt,
        },
        "pvc_mounts": [
            {
                "pvc": "irods-pvc",
                "mount_path": "/workspace/v1",
                "sub_path": model_id,
                "read_only": False,
            }
        ],
    }


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


@router.post("/runs/{run_id}", response_model=AnnotateRunResponse, status_code=201)
async def post_run(
    run_id: str,
    execution_client: ExecutionClientDep,
    settings: SettingsDep,
    principal: AuthenticatedPrincipalDep,
) -> AnnotateRunResponse:
    """Build the annotation job payload server-side and submit it to the
    Execution service.

    ``run_id`` doubles as the model identifier — the payload is built from
    server-side settings and the authenticated principal; nothing sensitive is
    passed from the browser.
    """
    # Build job payload server-side using run_id as the model identifier.
    job_payload = _build_annotation_payload(run_id, principal.subject, settings)

    # Submit to execution service.
    execution_status = await execution_client.post_run(run_id, job_payload)

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

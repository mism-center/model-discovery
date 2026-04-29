"""Run-scoped endpoints — orchestrate Discovery DAL + Execution service.

GET /runs/{run_id} hits the Execution API first so its lazy DAL refresh
fires, then reads the run back from the DAL with the freshly-updated status.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, Query

from mismapi.api.v1._run_helpers import resource_summary, run_detail
from mismapi.clients.execution_client import ExecutionClient
from mismapi.dependencies.execution import get_execution_client
from mismapi.dependencies.registry import get_registry_service
from mismapi.schemas.registry import RunDetailResponse
from mismapi.services.registry_service import RegistryService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/runs/{run_id}", response_model=RunDetailResponse)
async def get_run(
    run_id: str,
    refresh: bool = Query(
        default=True,
        description=(
            "When true (default), call the Execution service first so its lazy "
            "DAL refresh fires before we read the Run record — guaranteeing the "
            "freshest status. Set to false to skip the round-trip and return "
            "whatever the DAL has cached (cheap; useful for list-row previews)."
        ),
    ),
    service: RegistryService = Depends(get_registry_service),
    execution_client: ExecutionClient = Depends(get_execution_client),
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

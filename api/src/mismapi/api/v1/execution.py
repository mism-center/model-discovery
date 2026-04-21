from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends

from mismapi.auth.base import AuthenticatedPrincipal, require_principal
from mismapi.core.deps import HelxExecutionClientDep, SettingsDep
from mismapi.core.errors import APIError
from mismapi.schemas.execution import ExecutionStartRequest, ExecutionStartResponse

router = APIRouter()


@router.post("/executions", response_model=ExecutionStartResponse)
async def execute_run(
    _principal: Annotated[AuthenticatedPrincipal, Depends(require_principal)],
    settings: SettingsDep,
    helx_client: HelxExecutionClientDep,
    payload: ExecutionStartRequest | None = None,
) -> ExecutionStartResponse:
    if not settings.stub_upstream_services and not settings.helx_exec_platform_base_url:
        raise APIError(
            status_code=503,
            code="execution_exec_platform_unconfigured",
            detail="HeLx Execution Platform base URL is not configured.",
        )

    body: dict[str, Any] = {}
    if payload is not None:
        if payload.model_id is not None:
            body["model_id"] = payload.model_id
        if payload.parameters is not None:
            body["parameters"] = payload.parameters

    helx_result = await helx_client.execute(request_body=body)

    state: Literal["accepted", "running"] = (
        "accepted" if helx_result.http_status == 202 else "running"
    )
    message = (
        "Execution was accepted and is starting."
        if helx_result.http_status == 202
        else "Execution has started."
    )

    return ExecutionStartResponse(
        state=state,
        message=message,
        execution_id=helx_result.execution_id,
        upstream_http_status=helx_result.http_status,
        poll_after_seconds=5,
    )

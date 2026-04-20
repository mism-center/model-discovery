from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends

from mismapi.auth.base import (
    AuthenticatedPrincipal,
    require_principal,
    subject_access_token_for_upstream_exchange,
)
from mismapi.core.deps import (
    HelxExecutionClientDep,
    OIDCServiceDep,
    OIDCValidatorDep,
    SettingsDep,
)
from mismapi.core.errors import APIError
from mismapi.schemas.execution import ExecutionStartRequest, ExecutionStartResponse

router = APIRouter()


@router.post("/executions", response_model=ExecutionStartResponse)
async def execute_run(
    principal: Annotated[AuthenticatedPrincipal, Depends(require_principal)],
    subject_access_token: Annotated[str, Depends(subject_access_token_for_upstream_exchange)],
    settings: SettingsDep,
    validator: OIDCValidatorDep,
    oidc_service: OIDCServiceDep,
    helx_client: HelxExecutionClientDep,
    payload: ExecutionStartRequest | None = None,
) -> ExecutionStartResponse:
    audience = settings.oidc_token_exchange_audience.strip()
    if not audience:
        raise APIError(
            status_code=503,
            code="execution_token_exchange_unconfigured",
            detail="OIDC token exchange audience is not configured.",
        )
    if not settings.stub_upstream_services and not settings.helx_exec_platform_base_url.strip():
        raise APIError(
            status_code=503,
            code="execution_exec_platform_unconfigured",
            detail="HeLx Execution Platform base URL is not configured.",
        )

    exchanged = await oidc_service.exchange_for_audience(
        subject_access_token=subject_access_token,
        audience=audience,
    )

    aud = settings.helx_exec_platform_jwt_audience_effective
    await validator.validate_upstream_access_token(
        exchanged.access_token,
        expected_audience=aud,
        expected_subject=principal.subject,
    )

    body: dict[str, Any] = {}
    if payload is not None:
        if payload.model_id is not None:
            body["model_id"] = payload.model_id
        if payload.parameters is not None:
            body["parameters"] = payload.parameters

    helx_result = await helx_client.execute(
        bearer_access_token=exchanged.access_token,
        request_body=body,
    )

    state: Literal["accepted", "running"] = (
        "accepted" if helx_result.http_status == 202 else "running"
    )
    message = (
        "Execution was accepted and is starting."
        if helx_result.http_status == 202
        else "Execution has started."
    )

    ttl = exchanged.expires_in if exchanged.expires_in > 0 else None

    return ExecutionStartResponse(
        state=state,
        message=message,
        execution_id=helx_result.execution_id,
        upstream_http_status=helx_result.http_status,
        poll_after_seconds=5,
        exchanged_access_token_ttl_seconds=ttl,
    )

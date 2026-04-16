from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Request

from mismapi.auth.base import (
    AuthenticatedPrincipal,
    require_principal,
    subject_access_token_for_upstream_exchange,
)
from mismapi.auth.oidc import exchange_access_token_for_audience
from mismapi.auth.oidc_auth_validator import OIDCAuthValidator
from mismapi.clients.helx_execution_client import HelxExecutionClient
from mismapi.core.errors import APIError
from mismapi.schemas.execution import ExecutionStartRequest, ExecutionStartResponse

router = APIRouter()


@router.post("/runs", response_model=ExecutionStartResponse)
async def execute_run(
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_principal)],
    subject_access_token: Annotated[str, Depends(subject_access_token_for_upstream_exchange)],
    payload: ExecutionStartRequest | None = None,
) -> ExecutionStartResponse:
    settings = request.app.state.settings
    if settings.auth_mode != "oidc":
        raise APIError(
            status_code=503,
            code="execution_oidc_only",
            detail="Model execution requires OIDC authentication.",
        )
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

    validator = request.app.state.auth_validator
    if not isinstance(validator, OIDCAuthValidator):
        raise APIError(
            status_code=503,
            code="execution_oidc_validator_required",
            detail="Model execution requires OIDC token validation.",
        )

    discovery_loader = request.app.state.oidc_discovery_loader
    discovery = await discovery_loader.load()

    exchanged = await exchange_access_token_for_audience(
        discovery,
        settings,
        subject_access_token=subject_access_token,
        audience=audience,
    )

    aud = settings.helx_exec_platform_jwt_audience_effective
    await validator.validate_upstream_access_token(
        exchanged.access_token,
        expected_audience=aud,
        expected_subject=principal.subject,
    )

    helx_client: HelxExecutionClient = request.app.state.helx_execution_client
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

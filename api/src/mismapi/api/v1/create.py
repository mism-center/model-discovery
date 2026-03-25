import logging

from fastapi import APIRouter, Depends, Request

from mismapi.auth.base import AuthenticatedPrincipal, require_principal
from mismapi.schemas.registry import (
    CreateRunRequest,
    CreateRunResponse,
    RegisterModelRequest,
    RegisterModelResponse,
    UpdateModelRequest,
)
from mismapi.services.registry_service import RegistryService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/models", response_model=RegisterModelResponse, status_code=201)
async def create_model(
    request: Request,
    payload: RegisterModelRequest,
    principal: AuthenticatedPrincipal = Depends(require_principal),
) -> RegisterModelResponse:
    service: RegistryService = request.app.state.registry_service

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
    request: Request,
    model_id: str,
    payload: UpdateModelRequest,
    principal: AuthenticatedPrincipal = Depends(require_principal),
) -> RegisterModelResponse:
    service: RegistryService = request.app.state.registry_service

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
    response_model=CreateRunResponse,
    status_code=201,
)
async def create_run(
    request: Request,
    model_id: str,
    payload: CreateRunRequest,
    principal: AuthenticatedPrincipal = Depends(require_principal),
) -> CreateRunResponse:
    service: RegistryService = request.app.state.registry_service

    run = service.create_run(
        principal,
        model_id=model_id,
        input_resource_ids=payload.input_resource_ids,
        parameters=payload.parameters,
        triggered_by=payload.triggered_by,
        notes=payload.notes,
    )

    return CreateRunResponse(
        id=run.id,
        model_id=run.model_id,
        model_version=run.model_version,
        status=run.status.value,
        input_resource_ids=list(run.input_resource_ids),
        created_at=run.created_at,
    )

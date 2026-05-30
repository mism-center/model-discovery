import logging

from fastapi import APIRouter, Query

from mismapi.auth.base import AuthenticatedPrincipalDep
from mismapi.core.deps import RegistryServiceDep, SessionStoreDep, SettingsDep
from mismapi.schemas.registry import (
    CreateRunRequest,
    CreateRunResponse,
    RegisterModelRequest,
    RegisterModelResponse,
    UpdateModelRequest,
)
from mismapi.schemas.search import ModelListItem, ModelListResponse
from mismapi.schemas.upload import UploadInitiatedResponse
from mismapi.utils import UPLOAD_ALLOWED_PATH_TEMPLATE

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/models", response_model=ModelListResponse)
async def list_models(
    service: RegistryServiceDep,
    name: str | None = Query(default=None, description="Substring match on model name"),
    owner: str | None = Query(default=None, description="Exact match on owner"),
    tags: list[str] | None = Query(default=None, description="Format tags (all must match)"),
    organisms: list[str] | None = Query(default=None, description="Organisms (any must match)"),
    scales: list[str] | None = Query(default=None, description="Modeling scales (any must match)"),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
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
    service: RegistryServiceDep,
    principal: AuthenticatedPrincipalDep,
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
        owner=resource.owner,
        description=resource.description,
        created_at=resource.created_at,
    )


@router.put("/models/{model_id}", response_model=RegisterModelResponse)
async def update_model(
    model_id: str,
    payload: UpdateModelRequest,
    service: RegistryServiceDep,
    principal: AuthenticatedPrincipalDep,
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
        owner=resource.owner,
        description=resource.description,
        created_at=resource.created_at,
    )


@router.post("/models/{model_id}/upload", response_model=UploadInitiatedResponse)
async def upload_model_file(
    model_id: str,
    settings: SettingsDep,
    session_store: SessionStoreDep,
    service: RegistryServiceDep,
    principal: AuthenticatedPrincipalDep,
) -> UploadInitiatedResponse:

    service.get_resource_and_assert_ownership(principal, resource_id=model_id)
    allowed_path = UPLOAD_ALLOWED_PATH_TEMPLATE.format(resource_id=model_id)
    token = await session_store.mint_upload_token(
        principal.subject,
        settings.upload_max_bytes,
        allowed_path,
    )

    return UploadInitiatedResponse(
        upload_server_base_url=settings.tusd_base_url,
        resource_id=model_id,
        token=token,
    )


@router.post(
    "/models/{model_id}/runs",
    response_model=CreateRunResponse,
    status_code=201,
)
async def create_run(
    model_id: str,
    payload: CreateRunRequest,
    service: RegistryServiceDep,
    principal: AuthenticatedPrincipalDep,
) -> CreateRunResponse:

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

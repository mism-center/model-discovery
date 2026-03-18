from fastapi import APIRouter, Request

from mismapi.clients.upload_client import UploadServiceClient
from mismapi.schemas.common import ModelId
from mismapi.schemas.upload import (
    ModelMetadataPayload,
    ModelMetadataUpsertResponse,
)

router = APIRouter()


@router.post("/models", response_model=ModelMetadataUpsertResponse)
async def create_model(
    request: Request,
    payload: ModelMetadataPayload,
) -> ModelMetadataUpsertResponse:
    upload_client: UploadServiceClient = request.app.state.upload_client
    created = await upload_client.create_model(
        name=payload.name,
        description=payload.description,
        version=payload.version,
        metadata=payload.metadata,
    )
    return ModelMetadataUpsertResponse(model_id=created.model_id, tracking_id=created.tracking_id)


@router.put("/models/{model_id}", response_model=ModelMetadataUpsertResponse)
async def update_model(
    request: Request,
    model_id: ModelId,
    payload: ModelMetadataPayload,
) -> ModelMetadataUpsertResponse:
    upload_client: UploadServiceClient = request.app.state.upload_client
    updated = await upload_client.update_model(
        model_id=model_id,
        name=payload.name,
        description=payload.description,
        version=payload.version,
        metadata=payload.metadata,
    )
    return ModelMetadataUpsertResponse(model_id=updated.model_id, tracking_id=updated.tracking_id)

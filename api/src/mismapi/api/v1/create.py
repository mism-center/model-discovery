from fastapi import APIRouter

from mismapi.core.deps import UploadClientDep
from mismapi.schemas.common import ModelId
from mismapi.schemas.upload import (
    ModelMetadataPayload,
    ModelMetadataUpsertResponse,
)

router = APIRouter()


@router.post("/models", response_model=ModelMetadataUpsertResponse)
async def create_model(
    payload: ModelMetadataPayload,
    upload_client: UploadClientDep,
) -> ModelMetadataUpsertResponse:
    created = await upload_client.create_model(
        name=payload.name,
        description=payload.description,
        version=payload.version,
        metadata=payload.metadata,
    )
    return ModelMetadataUpsertResponse(model_id=created.model_id, tracking_id=created.tracking_id)


@router.put("/models/{model_id}", response_model=ModelMetadataUpsertResponse)
async def update_model(
    model_id: ModelId,
    payload: ModelMetadataPayload,
    upload_client: UploadClientDep,
) -> ModelMetadataUpsertResponse:
    updated = await upload_client.update_model(
        model_id=model_id,
        name=payload.name,
        description=payload.description,
        version=payload.version,
        metadata=payload.metadata,
    )
    return ModelMetadataUpsertResponse(model_id=updated.model_id, tracking_id=updated.tracking_id)

from fastapi import APIRouter, Request

from mism_api.clients.upload_client import UploadServiceClient
from mism_api.core.errors import APIError
from mism_api.schemas.upload import ModelMetadataUpsertRequest, ModelMetadataUpsertResponse

router = APIRouter()


@router.post("/models", response_model=ModelMetadataUpsertResponse)
async def create_model(
    request: Request,
    payload: ModelMetadataUpsertRequest,
) -> ModelMetadataUpsertResponse:
    upload_client: UploadServiceClient = request.app.state.upload_client
    created = await upload_client.create_model(
        name=payload.name,
        description=payload.description,
        version=payload.version,
        metadata=payload.metadata,
    )
    return ModelMetadataUpsertResponse(model_id=created.model_id, tracking_id=created.tracking_id)


@router.put("/models", response_model=ModelMetadataUpsertResponse)
async def update_model(
    request: Request,
    payload: ModelMetadataUpsertRequest,
) -> ModelMetadataUpsertResponse:
    model_id = (payload.model_id or "").strip()
    if not model_id:
        raise APIError(
            status_code=422,
            code="model_id_required",
            detail="model_id is required for PUT /models metadata updates.",
        )

    upload_client: UploadServiceClient = request.app.state.upload_client
    updated = await upload_client.update_model(
        model_id=model_id,
        name=payload.name,
        description=payload.description,
        version=payload.version,
        metadata=payload.metadata,
    )
    return ModelMetadataUpsertResponse(model_id=updated.model_id, tracking_id=updated.tracking_id)

from pydantic import BaseModel, Field

from schemas.common import CustomMetadata, ModelId


class ModelMetadataPayload(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None
    version: str | None = None
    metadata: CustomMetadata = Field(default_factory=dict)


# This model is used for both create and update responses
class ModelMetadataUpsertResponse(BaseModel):
    status: str = Field(default="accepted")
    model_id: ModelId
    tracking_id: str | None = None


class UploadAcceptedResponse(BaseModel):
    status: str = Field(default="accepted")
    model_id: ModelId
    upload_id: str
    tracking_id: str
    filename: str
    content_type: str | None = None
    bytes_received: int = Field(ge=0)
    parts_uploaded: int = Field(ge=0)

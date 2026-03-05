from pydantic import BaseModel, Field

from mism_api.schemas.common import CustomMetadata


class ModelMetadataUpsertRequest(BaseModel):
    model_id: str | None = None
    name: str = Field(min_length=1)
    description: str | None = None
    version: str | None = None
    metadata: CustomMetadata = Field(default_factory=dict)


class ModelMetadataUpsertResponse(BaseModel):
    status: str = Field(default="accepted")
    model_id: str
    tracking_id: str | None = None


class UploadAcceptedResponse(BaseModel):
    status: str = Field(default="accepted")
    model_id: str
    upload_id: str
    tracking_id: str
    filename: str
    content_type: str | None = None
    bytes_received: int = Field(ge=0)
    parts_uploaded: int = Field(ge=0)

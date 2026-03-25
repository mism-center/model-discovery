from pydantic import BaseModel, Field

from mismapi.schemas.common import ModelId


class UploadAcceptedResponse(BaseModel):
    status: str = Field(default="accepted")
    model_id: ModelId
    upload_id: str
    tracking_id: str
    filename: str
    content_type: str | None = None
    bytes_received: int = Field(ge=0)
    parts_uploaded: int = Field(ge=0)

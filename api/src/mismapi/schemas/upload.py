from pydantic import BaseModel, Field


class UploadInitiatedResponse(BaseModel):
    upload_server_base_url: str
    resource_id: str
    token: str


class UploadAcceptedResponse(BaseModel):
    status: str = Field(default="accepted")
    # Resource the upload was scoped to — model, dataset, or any other registry resource.
    resource_id: str
    upload_id: str
    tracking_id: str
    filename: str
    content_type: str | None = None
    bytes_received: int = Field(ge=0)
    parts_uploaded: int = Field(ge=0)

    # `model_` is a Pydantic-protected namespace; we have no `model_` fields here,
    # but this guards against future renames re-introducing the warning.
    model_config = {"protected_namespaces": ()}

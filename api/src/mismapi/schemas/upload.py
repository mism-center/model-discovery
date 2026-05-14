from pydantic import BaseModel


class UploadInitiatedResponse(BaseModel):
    upload_server_base_url: str
    resource_id: str
    token: str

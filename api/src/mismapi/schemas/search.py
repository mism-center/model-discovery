from datetime import datetime

from pydantic import BaseModel, Field


class ModelListItem(BaseModel):
    id: str
    name: str
    resource_type: str
    location_uri: str
    execution_type: str | None = None
    version: str = ""
    status: str
    owner: str = ""
    description: str = ""
    created_at: datetime


class ModelListResponse(BaseModel):
    total: int = Field(ge=0)
    results: list[ModelListItem]

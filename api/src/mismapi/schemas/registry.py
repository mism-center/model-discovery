from datetime import datetime
from typing import Any

from mism_registry import ExecutionType
from pydantic import BaseModel, Field


class RegisterModelRequest(BaseModel):
    name: str
    location_uri: str
    execution_type: ExecutionType
    description: str = ""
    version: str = ""
    owner: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class RegisterModelResponse(BaseModel):
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


class UpdateModelRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    version: str | None = None
    owner: str | None = None
    location_uri: str | None = None
    execution_type: ExecutionType | None = None
    metadata: dict[str, Any] | None = None


class RegisterDatasetRequest(BaseModel):
    name: str
    location_uri: str
    description: str = ""
    version: str = ""
    owner: str = ""
    format_tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RegisterDatasetResponse(BaseModel):
    id: str
    name: str
    resource_type: str
    location_uri: str
    description: str = ""
    version: str = ""
    status: str
    owner: str = ""
    format_tags: list[str] = Field(default_factory=list)
    created_at: datetime


class UpdateDatasetRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    version: str | None = None
    owner: str | None = None
    location_uri: str | None = None
    format_tags: list[str] | None = None
    metadata: dict[str, Any] | None = None


class CreateRunRequest(BaseModel):
    input_resource_ids: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    triggered_by: str = ""
    notes: str = ""


class CreateRunResponse(BaseModel):
    id: str
    model_id: str
    model_version: str = ""
    status: str
    input_resource_ids: list[str] = Field(default_factory=list)
    created_at: datetime

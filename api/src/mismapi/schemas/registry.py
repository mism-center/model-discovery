from datetime import datetime
from typing import Any, Literal

from mism_registry import ExecutionType
from pydantic import BaseModel, Field


class RegisterModelRequest(BaseModel):
    name: str
    location_uri: str
    execution_type: ExecutionType
    execution_ref: str | None = None
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
    execution_ref: str | None = None
    version: str = ""
    status: str
    created_at: datetime


class UpdateModelRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    version: str | None = None
    owner: str | None = None
    location_uri: str | None = None
    execution_type: ExecutionType | None = None
    metadata: dict[str, Any] | None = None
    execution_ref: str | None = None


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


class ExecuteRunRequest(BaseModel):
    """Create a run AND trigger execution on the Execution API."""

    input_resource_ids: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    triggered_by: str = ""
    notes: str = ""
    mode: Literal["batch", "interactive"] = "batch"


class ExecuteRunResponse(BaseModel):
    """Combined response: run record + execution launch result."""

    id: str
    model_id: str
    model_version: str = ""
    status: str
    input_resource_ids: list[str] = Field(default_factory=list)
    created_at: datetime
    execution: dict[str, Any] = Field(
        default_factory=dict,
        description="Raw response from the Execution API (batch or interactive).",
    )


# ── Model run details (UI: model runs page) ──────────────────────────


class ResourceSummaryItem(BaseModel):
    """Lightweight summary of a Resource for embedding inside run detail responses."""

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


class RunDetailItem(BaseModel):
    """Full Run record as returned to the UI."""

    id: str
    model_id: str
    model_version: str = ""
    status: str
    input_resource_ids: list[str] = Field(default_factory=list)
    output_resource_ids: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str = ""
    log_uri: str = ""
    triggered_by: str = ""
    notes: str = ""
    created_at: datetime

    model_config = {"protected_namespaces": ()}


class ModelRunDetailItem(BaseModel):
    """A run enriched with hydrated input and output resources."""

    run: RunDetailItem
    input_resources: list[ResourceSummaryItem] = Field(default_factory=list)
    output_resources: list[ResourceSummaryItem] = Field(default_factory=list)


class ModelRunDetailsResponse(BaseModel):
    """All runs for a model, with the model summary and hydrated run details."""

    model: ResourceSummaryItem
    runs: list[ModelRunDetailItem] = Field(default_factory=list)
    total: int

    model_config = {"protected_namespaces": ()}

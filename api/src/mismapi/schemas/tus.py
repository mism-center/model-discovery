"""
Pydantic models for tusd HTTP hook requests and responses.

tusd posts a `HookRequest` envelope to a configured HTTP endpoint for each
hook event (`pre-create`, `post-finish`, etc.). Schema reference:
https://tus.github.io/tusd/advanced-topics/hooks/#http-hooks

We intentionally model only the subset we read or return; tusd ignores
unknown response fields and we ignore unknown request fields (`extra="allow"`)
to stay forward-compatible across tusd minor versions.

The resource being uploaded is identified via `Event.Upload.MetaData.resource_id`.
The upload client (web frontend or CLI) is responsible for setting this
metadata key when creating the tus upload.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# tusd posts and expects PascalCase JSON. We mirror that on the wire via
# Pydantic field aliases while keeping snake_case attribute names in
# Python. Routes returning these models must pass `response_model_by_alias=True`
# so FastAPI serializes with the aliases tusd understands.


class TusUpload(BaseModel):
    """tusd Upload object inside a HookRequest event."""

    model_config = ConfigDict(extra="allow", validate_by_name=True, validate_by_alias=True)

    id: str = Field(alias="ID")
    size: int | None = Field(default=None, alias="Size")
    offset: int = Field(default=0, alias="Offset")
    is_final: bool = Field(default=False, alias="IsFinal")
    is_partial: bool = Field(default=False, alias="IsPartial")
    metadata: dict[str, str] = Field(default_factory=dict, alias="MetaData")
    storage: dict[str, Any] | None = Field(default=None, alias="Storage")


class TusHTTPRequest(BaseModel):
    model_config = ConfigDict(extra="allow", validate_by_name=True, validate_by_alias=True)

    method: str = Field(default="", alias="Method")
    uri: str = Field(default="", alias="URI")
    remote_addr: str = Field(default="", alias="RemoteAddr")
    header: dict[str, list[str]] = Field(default_factory=dict, alias="Header")


class TusEvent(BaseModel):
    model_config = ConfigDict(extra="allow", validate_by_name=True, validate_by_alias=True)

    upload: TusUpload = Field(alias="Upload")
    http_request: TusHTTPRequest | None = Field(default=None, alias="HTTPRequest")


class TusHookRequest(BaseModel):
    """Top-level envelope tusd posts to a hook endpoint."""

    model_config = ConfigDict(extra="allow", validate_by_name=True, validate_by_alias=True)

    type: str = Field(default="", alias="Type")
    event: TusEvent = Field(alias="Event")


class TusHTTPResponse(BaseModel):
    """Response sub-object tusd uses to construct the client-facing reply."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    status_code: int = Field(default=200, alias="StatusCode")
    body: str = Field(default="", alias="Body")
    header: dict[str, str] = Field(default_factory=dict, alias="Header")


class TusHookResponse(BaseModel):
    """
    Response shape tusd expects from a hook endpoint.

    For pre-create: setting `reject_upload=True` aborts the upload; tusd
    returns the embedded `http_response` to the client.
    For post-finish: tusd ignores the body but does check the HTTP status
    code of our reply, so we still return a valid envelope.
    """

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    http_response: TusHTTPResponse = Field(default_factory=TusHTTPResponse, alias="HTTPResponse")
    reject_upload: bool = Field(default=False, alias="RejectUpload")

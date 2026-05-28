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
    storage: Storage | None = Field(default=None, alias="Storage")


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

    """
    HTTPResponse's fields can be filled to modify the HTTP response.
    This is only possible for pre-create, pre-finish and post-receive hooks.
    For other hooks this value is ignored.
    If multiple hooks modify the HTTP response, a later hook may overwrite the
    modified values from a previous hook (e.g. if multiple post-receive hooks
    are executed).
    Example usages: Send an error to the client if RejectUpload/StopUpload are
    set in the pre-create/post-receive hook. Send more information to the client
    in the pre-finish hook.
    """
    http_response: TusHTTPResponse = Field(default_factory=TusHTTPResponse, alias="HTTPResponse")

    """
    RejectUpload will cause the upload to be rejected and not be created during
    POST request. This value is only respected for pre-create hooks. For other hooks,
    it is ignored. Use the HTTPResponse field to send details about the rejection
    to the client.
    """
    reject_upload: bool = Field(default=False, alias="RejectUpload")

    """
    RejectTermination will cause the termination of the upload to be rejected, keeping the upload.
    This value is only respected for pre-terminate hooks. For other hooks,
    it is ignored. Use the HTTPResponse field to send details about the rejection
    to the client.
    """
    reject_termination: bool = Field(default=False, alias="RejectTermination")

    """
    ChangeFileInfo can be set to change selected properties of an upload before
    it has been created. See the handler.FileInfoChanges type for more details.
    Changes are applied on a per-property basis, meaning that specifying just
    one property leaves all others unchanged.
    This value is only respected for pre-create hooks.
    """
    change_file_info: FileInfoChanges | None = Field(default=None, alias="ChangeFileInfo")


class FileInfoChanges(BaseModel):
    """
    FileInfoChanges holds the changes to be applied to an upload's file info.
    This class's name is different from the handler.FileInfoChanges because that's the way
    it's named in the TUS protocol.
    """

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    """
    If ID is not empty, it will be passed to the data store, allowing hooks to
    influence the upload ID. This field is also used as the base path for
    the info file stored on the data store.
    """
    id: str | None = Field(default=None, alias="ID")

    """
    If MetaData is not nil, it replaces the entire user-defined meta data from
    the upload creation request. You can add custom meta data fields this way
    or ensure that only certain fields from the user-defined meta data are saved.
    If you want to retain only specific entries from the user-defined meta data, you must
    manually copy them into this MetaData field.
    If you do not want to store any meta data, set this field to an empty map (`MetaData{}`).
    If you want to keep the entire user-defined meta data, set this field to nil.
    """
    metadata: dict[str, str] | None = Field(default=None, alias="MetaData")

    """
    If Storage is not nil, it is passed to the data store to allow for minor adjustments
    to the upload storage (e.g. destination file name).
    """
    storage: Storage | None = Field(default=None, alias="Storage")


class Storage(BaseModel):
    """
    Storage contains information about where the upload is stored. The exact values depend
    on the storage that is used and are not available in the pre-create hook.

    Storage can be used to customize the location where the uploaded file (aka the binary
    file) is saved. The exact behavior depends on the storage that is used. Please note
    that this only influences the location of the binary file. tusd will still create an
    info file whose location is derived from the upload ID and cannot be customized using
    this ChangeFileInfo.Storage property, but only using ChangeFileInfo.ID.

    The location can contain forward slashes (/) to store uploads in a hierarchical structure,
    such as nested directories.

    Similar to ChangeFileInfo.ID, tusd will not check whether a file is already saved under
    this location and might overwrite it. It is the hooks responsibility to ensure that
    the location is safe to use. A good approach is to embed a random part (e.g. a UUID) in
    the location.
    """

    """
    When the filestore is used, the Path property defines where the uploaded file is saved.
    The path may be absolute or relative, and point towards a location outside of the directory
    defined using the `-dir` flag. If it's relative, the path will be resolved relative to `-dir`.
    """
    path: str | None = Field(default=None, alias="Path")

    """
    When the filestore is used, the InfoPath property defines where the info file is saved.
    """
    info_path: str | None = Field(default=None, alias="InfoPath")

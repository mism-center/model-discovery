from typing import Literal

from pydantic import BaseModel, Field


class ExecutionStartRequest(BaseModel):
    """Optional payload forwarded to HeLx; extend when the HeLx contract stabilizes."""

    model_id: str | None = Field(
        default=None,
        description="Logical model identifier when applicable.",
    )
    parameters: dict[str, object] | None = Field(
        default=None,
        description="Optional execution parameters for HeLx.",
    )


class ExecutionStartResponse(BaseModel):
    """
    Response for the UI after the gateway has called HeLx.

    The UI should treat `execution_id` as an opaque handle for polling a future status endpoint
    (not implemented here). `poll_after_seconds` is a hint for backoff between polls.
    """

    state: Literal["accepted", "running"] = Field(
        description="High-level lifecycle state derived from HeLx HTTP semantics.",
    )
    message: str = Field(description="Human-readable status for display.")
    execution_id: str | None = Field(
        default=None,
        description="Opaque id from HeLx when present; use for status polling.",
    )
    upstream_http_status: int = Field(description="HTTP status returned by HeLx execute.")
    poll_after_seconds: int = Field(
        default=5,
        ge=1,
        description="Suggested delay before the first status poll.",
    )

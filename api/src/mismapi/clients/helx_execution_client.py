import logging
import uuid
from dataclasses import dataclass
from typing import Any

import httpx

from mismapi.core.errors import APIError
from mismapi.core.http_client import error_from_downstream_response

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class HelxExecuteResult:
    http_status: int
    execution_id: str | None
    payload: dict[str, object] | None


def _coerce_execution_id(data: dict[str, object]) -> str | None:
    for key in ("execution_id", "job_id", "run_id", "id"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


class HelxExecutionClient:
    def __init__(self, base_url: str, timeout_seconds: float, stub_upstream: bool = False) -> None:
        normalized = base_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=normalized, timeout=timeout_seconds)
        self._stub_upstream = stub_upstream

    async def close(self) -> None:
        await self._client.aclose()

    async def execute(self, *, request_body: dict[str, Any]) -> HelxExecuteResult:
        if self._stub_upstream:
            fake_id = str(uuid.uuid4())
            logger.info("helx_execute_stub execution_id=%s", fake_id)
            return HelxExecuteResult(
                http_status=202,
                execution_id=fake_id,
                payload={"status": "accepted", "execution_id": fake_id},
            )

        try:
            response = await self._client.post(
                "/api/v1/execute",
                json=request_body,
            )
        except httpx.HTTPError as exc:
            logger.error("helx_execute_transport_error error=%s", type(exc).__name__)
            raise APIError(
                status_code=502,
                code="helx_execute_unavailable",
                detail="HeLx Execution Platform request failed.",
            ) from exc

        status = response.status_code
        if status in (200, 202):
            parsed: dict[str, object] | None = None
            try:
                raw = response.json()
            except ValueError:
                raw = None
            if isinstance(raw, dict):
                parsed = raw
            execution_id = _coerce_execution_id(parsed) if parsed else None
            return HelxExecuteResult(
                http_status=status,
                execution_id=execution_id,
                payload=parsed,
            )

        if 400 <= status < 500:
            mapped_status, code, detail = error_from_downstream_response(
                response,
                fallback_code="helx_execute_client_error",
                fallback_detail="HeLx Execution Platform rejected the execution request.",
            )
            raise APIError(status_code=mapped_status, code=code, detail=detail)

        logger.error("helx_execute_unexpected_status status=%s", status)
        raise APIError(
            status_code=502,
            code="helx_execute_bad_response",
            detail="HeLx Execution Platform returned an unexpected response.",
        )

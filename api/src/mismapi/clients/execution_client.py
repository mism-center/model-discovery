import logging
from uuid import uuid4

import httpx

from mismapi.core.errors import APIError
from mismapi.core.http_client import error_from_downstream_response

logger = logging.getLogger(__name__)


class ExecutionClient:
    """HTTP client for the MISM Execution API.

    Mirrors the contract exercised by test_batch_execution.py and
    test_interactive_session.py:
      - POST /api/v1/runs          {"run_id": ...}  → batch execution
      - POST /api/v1/runs/{id}/interactive           → interactive session
      - GET  /api/v1/runs/{id}                       → status polling
    """

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 120.0,
        stub_upstream: bool = False,
    ) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout_seconds)
        self._stub_upstream = stub_upstream

    # ── Batch execution ─────────────────────────────────────────────

    async def launch_batch(self, run_id: str) -> dict:
        """POST /api/v1/runs  →  trigger headless execution."""
        if self._stub_upstream:
            logger.info("Execution service (stub) launch_batch run_id=%s", run_id)
            return {"run_id": run_id, "status": "registered", "stub": True}

        return await self._post("/api/v1/runs", json={"run_id": run_id}, expected=201)

    # ── Interactive session ─────────────────────────────────────────

    async def launch_interactive(self, run_id: str) -> dict:
        """POST /api/v1/runs/{run_id}/interactive  →  start interactive session."""
        if self._stub_upstream:
            sid = f"stub-sid-{uuid4().hex[:8]}"
            logger.info("Execution service (stub) launch_interactive run_id=%s sid=%s", run_id, sid)
            return {"run_id": run_id, "sid": sid, "url": f"https://stub/{sid}", "stub": True}

        return await self._post(f"/api/v1/runs/{run_id}/interactive", expected=201)

    # ── Status polling ──────────────────────────────────────────────

    async def get_status(self, run_id: str) -> dict:
        """GET /api/v1/runs/{run_id}  →  current status + phase."""
        if self._stub_upstream:
            return {"run_id": run_id, "status": "completed", "phase": "stub", "stub": True}

        try:
            response = await self._client.get(f"/api/v1/runs/{run_id}")
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException as exc:
            raise APIError(
                status_code=504,
                code="execution_status_timeout",
                detail=f"Execution service status poll timed out for run {run_id}.",
            ) from exc
        except httpx.HTTPStatusError as exc:
            status, code, detail = error_from_downstream_response(
                exc.response,
                fallback_code="execution_status_failed",
                fallback_detail=f"Failed to get execution status for run {run_id}.",
            )
            raise APIError(status_code=status, code=code, detail=detail) from exc
        except httpx.HTTPError as exc:
            raise APIError(
                status_code=502,
                code="execution_status_failed",
                detail=f"Failed to reach execution service for run {run_id}.",
            ) from exc

    # ── Lifecycle ───────────────────────────────────────────────────

    async def close(self) -> None:
        await self._client.aclose()

    # ── Internal ────────────────────────────────────────────────────

    async def _post(
        self,
        url: str,
        json: dict | None = None,
        expected: int = 201,
    ) -> dict:
        action = url.rsplit("/", 1)[-1] or "runs"
        try:
            response = await self._client.post(url, json=json, follow_redirects=True)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise APIError(
                status_code=504,
                code=f"execution_{action}_timeout",
                detail=f"Execution service timed out on {url}.",
            ) from exc
        except httpx.HTTPStatusError as exc:
            status, code, detail = error_from_downstream_response(
                exc.response,
                fallback_code=f"execution_{action}_failed",
                fallback_detail=f"Execution service call failed: {url}.",
            )
            raise APIError(status_code=status, code=code, detail=detail) from exc
        except httpx.HTTPError as exc:
            raise APIError(
                status_code=502,
                code=f"execution_{action}_failed",
                detail=f"Failed to reach execution service: {url}.",
            ) from exc

        try:
            return response.json()
        except ValueError:
            return {"status_code": response.status_code}

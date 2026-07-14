import logging
from typing import Any, cast
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

    async def launch_batch(self, run_id: str) -> dict[str, Any]:
        """POST /api/v1/runs  →  trigger headless execution."""
        if self._stub_upstream:
            logger.info("Execution service (stub) launch_batch run_id=%s", run_id)
            return {"run_id": run_id, "status": "registered", "stub": True}

        return await self._post("/api/v1/runs", json={"run_id": run_id}, expected=201)

    # ── Interactive session ─────────────────────────────────────────

    async def launch_interactive(self, run_id: str) -> dict[str, Any]:
        """POST /api/v1/runs/{run_id}/interactive  →  start interactive session."""
        if self._stub_upstream:
            sid = f"stub-sid-{uuid4().hex[:8]}"
            logger.info("Execution service (stub) launch_interactive run_id=%s sid=%s", run_id, sid)
            return {"run_id": run_id, "sid": sid, "url": f"https://stub/{sid}", "stub": True}

        return await self._post(f"/api/v1/runs/{run_id}/interactive", expected=201)

    # ── Annotation ──────────────────────────────────────────────────

    async def annotate(
        self,
        resource_id: str,
        image: str,
        prompt: str,
        cpus: str = "1",
        memory: str = "4Gi",
        model: str = "gpt-5.6-luna",
        openai_base_url: str = "",
    ) -> dict[str, Any]:
        """POST /api/v1/annotations  →  kick off an annotation job.

        The LLM API key and base URL are injected server-side by the
        execution-platform from its own environment — never forwarded here.
        """
        if self._stub_upstream:
            logger.info(
                "Execution service (stub) annotate resource_id=%s image=%s",
                resource_id,
                image,
            )
            return {
                "resource_id": resource_id,
                "sid": f"stub-sid-{resource_id[:8]}",
                "registration_status": "annotating",
                "stub": True,
            }

        return await self._post(
            "/api/v1/annotations",
            json={
                "resource_id": resource_id,
                "image": image,
                "prompt": prompt,
                "cpus": cpus,
                "memory": memory,
                "extra_env": {"AI_MODEL": model, "AZURE_OPENAI_BASE_URL": openai_base_url},
            },
            expected=200,
        )

    # ── Status polling ──────────────────────────────────────────────

    async def get_status(self, run_id: str) -> dict[str, Any]:
        """GET /api/v1/runs/{run_id}  →  current status + phase."""
        if self._stub_upstream:
            return {"run_id": run_id, "status": "completed", "phase": "stub", "stub": True}

        try:
            response = await self._client.get(f"/api/v1/runs/{run_id}")
            response.raise_for_status()
            return cast(dict[str, Any], response.json())
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

    # ── Cancellation ────────────────────────────────────────────────

    async def cancel_run(self, run_id: str) -> dict[str, Any]:
        """DELETE /api/v1/runs/{run_id}  →  cancel a running execution.

        The exec service is expected to update the DAL run status to CANCELLED
        as part of this call. Returns whatever the exec service responds with.
        """
        if self._stub_upstream:
            logger.info("Execution service (stub) cancel_run run_id=%s", run_id)
            return {"run_id": run_id, "status": "cancelled", "stub": True}

        try:
            response = await self._client.delete(f"/api/v1/runs/{run_id}")
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise APIError(
                status_code=504,
                code="execution_cancel_timeout",
                detail=f"Execution service cancel timed out for run {run_id}.",
            ) from exc
        except httpx.HTTPStatusError as exc:
            status, code, detail = error_from_downstream_response(
                exc.response,
                fallback_code="execution_cancel_failed",
                fallback_detail=f"Failed to cancel execution for run {run_id}.",
            )
            raise APIError(status_code=status, code=code, detail=detail) from exc
        except httpx.HTTPError as exc:
            raise APIError(
                status_code=502,
                code="execution_cancel_failed",
                detail=f"Failed to reach execution service to cancel run {run_id}.",
            ) from exc

        # 204 No Content is valid; tolerate empty body.
        try:
            return cast(dict[str, Any], response.json())
        except ValueError:
            return {"run_id": run_id, "status_code": response.status_code}

    # ── Lifecycle ───────────────────────────────────────────────────

    async def close(self) -> None:
        await self._client.aclose()

    # ── Internal ────────────────────────────────────────────────────

    async def _post(
        self,
        url: str,
        json: dict[str, Any] | None = None,
        expected: int = 201,
    ) -> dict[str, Any]:
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
            return cast(dict[str, Any], response.json())
        except ValueError:
            return {"status_code": response.status_code}

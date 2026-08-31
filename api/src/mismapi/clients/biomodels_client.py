import asyncio
import logging

import httpx
from pydantic import ValidationError

from mismapi.core.errors import APIError
from mismapi.core.http_client import error_from_downstream_response
from mismapi.schemas.biomodels import BioModelsRecordDTO, normalize_model_id

logger = logging.getLogger(__name__)


class BioModelsClient:
    """HTTP client for the public BioModels repository API.

    Contract:
      - GET /{modelId}?format=json -> model metadata

    There is no bulk endpoint, so `get_models` fans out one request per
    model id under a concurrency cap.
    """

    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float = 15.0,
        max_concurrency: int = 8,
    ) -> None:
        self._base_url = base_url
        self._max_concurrency = max_concurrency
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout_seconds,
            follow_redirects=True,
            headers={
                "Accept": "application/json",
                "User-Agent": "mism-discovery-gateway (+https://github.com/mism-center)",
            },
        )

    @property
    def configured(self) -> bool:
        return bool(self._base_url)

    def model_url(self, model_id: str) -> str:
        return f"{self._base_url}/{model_id}"

    # ── Single record ───────────────────────────────────────────────

    async def get_model(self, model_id: str) -> BioModelsRecordDTO:
        """GET /{modelId} -> metadata for one model."""
        if not self.configured:
            raise APIError(
                status_code=503,
                code="biomodels_not_configured",
                detail="BioModels integration is not configured. Set BIOMODELS_API_URL.",
            )

        normalized = normalize_model_id(model_id)
        if normalized is None:
            raise APIError(
                status_code=400,
                code="biomodels_invalid_model_id",
                detail=f"'{model_id}' is not a BioModels model id.",
            )

        try:
            response = await self._client.get(f"/{normalized}", params={"format": "json"})
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise APIError(
                status_code=504,
                code="biomodels_timeout",
                detail=f"BioModels timed out fetching {normalized}.",
            ) from exc
        except httpx.HTTPStatusError as exc:
            status, code, detail = error_from_downstream_response(
                exc.response,
                fallback_code="biomodels_fetch_failed",
                fallback_detail=f"BioModels failed to return {normalized}.",
            )
            raise APIError(status_code=status, code=code, detail=detail) from exc
        except httpx.HTTPError as exc:
            raise APIError(
                status_code=502,
                code="biomodels_fetch_failed",
                detail=f"Failed to reach BioModels for {normalized}.",
            ) from exc

        # A path BioModels doesn't recognize is not a 404: it 302s to the
        # site's login page, which then answers 200 with HTML. A success
        # status therefore proves nothing — the body has to parse.
        try:
            record = BioModelsRecordDTO.model_validate(response.json())
        except (ValueError, ValidationError) as exc:
            raise APIError(
                status_code=502,
                code="biomodels_invalid_response",
                detail=f"BioModels returned an unparseable record for {normalized}.",
            ) from exc

        return record.model_copy(
            update={"identifier": normalized, "url": self.model_url(normalized)}
        )

    # ── Bulk best-effort ────────────────────────────────────────────

    async def get_models(self, model_ids: list[str]) -> dict[str, BioModelsRecordDTO]:
        """Fetch many models concurrently, keyed by model id.

        Best-effort: an id BioModels cannot serve is logged and omitted
        from the result rather than failing the batch. Callers treat this
        metadata as additive, so a BioModels outage shouldn't break them.
        """
        if not self.configured or not model_ids:
            return {}

        wanted = sorted({normalized for a in model_ids if (normalized := normalize_model_id(a))})
        if not wanted:
            return {}

        limit = asyncio.Semaphore(self._max_concurrency)

        async def fetch(model_id: str) -> BioModelsRecordDTO | None:
            async with limit:
                try:
                    return await self.get_model(model_id)
                except APIError as exc:
                    logger.info(
                        "biomodels_fetch_skipped model_id=%s status=%s code=%s",
                        model_id,
                        exc.status_code,
                        exc.code,
                    )
                    return None

        records = await asyncio.gather(*(fetch(a) for a in wanted))
        return {r.identifier: r for r in records if r is not None}

    # ── Lifecycle ───────────────────────────────────────────────────

    async def close(self) -> None:
        await self._client.aclose()

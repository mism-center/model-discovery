import logging

import httpx
from pydantic import ValidationError

from mismapi.core.errors import APIError
from mismapi.core.http_client import error_from_downstream_response
from mismapi.schemas.cairns import CairnsRecommendRequest, CairnsRecommendResponse

logger = logging.getLogger(__name__)


class CairnsClient:
    """HTTP client for the CAIRNS recommendation API.

    CAIRNS is (currently) unauthenticated, so a base URL is the only configuration.
    """

    def __init__(self, *, base_url: str, timeout_seconds: float = 180.0) -> None:
        self._base_url = base_url
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout_seconds)

    @property
    def configured(self) -> bool:
        return bool(self._base_url)

    # ── Recommendation ──────────────────────────────────────────────

    async def recommend(self, request: CairnsRecommendRequest) -> CairnsRecommendResponse:
        if not self.configured:
            raise APIError(
                status_code=503,
                code="cairns_not_configured",
                detail="CAIRNS integration is not configured. Set CAIRNS_API_URL.",
            )

        try:
            response = await self._client.post(
                "/recommend",
                json=request.model_dump(mode="json"),
                follow_redirects=True,
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise APIError(
                status_code=504,
                code="cairns_recommend_timeout",
                detail="CAIRNS timed out while answering the question.",
            ) from exc
        except httpx.HTTPStatusError as exc:
            status, code, detail = error_from_downstream_response(
                exc.response,
                fallback_code="cairns_recommend_failed",
                fallback_detail="CAIRNS failed to answer the question.",
            )
            raise APIError(status_code=status, code=code, detail=detail) from exc
        except httpx.HTTPError as exc:
            raise APIError(
                status_code=502,
                code="cairns_recommend_failed",
                detail="Failed to reach CAIRNS.",
            ) from exc

        try:
            return CairnsRecommendResponse.model_validate(response.json())
        except (ValueError, ValidationError) as exc:
            logger.warning("cairns_invalid_response status=%s", response.status_code)
            raise APIError(
                status_code=502,
                code="cairns_invalid_response",
                detail="CAIRNS returned a response the gateway could not parse.",
            ) from exc

    # ── Lifecycle ───────────────────────────────────────────────────

    async def close(self) -> None:
        await self._client.aclose()

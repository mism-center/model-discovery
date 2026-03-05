import logging

import httpx
from pydantic import ValidationError

from mism_api.core.errors import APIError
from mism_api.schemas.search import SearchResponse, SearchResultItem

logger = logging.getLogger(__name__)


class SearchServiceClient:
    def __init__(self, base_url: str, timeout_seconds: float, stub_upstream: bool = False) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout_seconds)
        self._stub_upstream = stub_upstream

    async def search(self, query: str, limit: int, offset: int) -> SearchResponse:
        if self._stub_upstream:
            logger.info(
                "Called search service (stub) query=%s limit=%s offset=%s",
                query,
                limit,
                offset,
            )
            return SearchResponse(
                total=1,
                results=[
                    SearchResultItem(
                        id="stub-model-1",
                        type="model",
                        name="Stub Model Result",
                        description="Stubbed search result from gateway.",
                        score=1.0,
                        metadata={
                            "query": query,
                            "limit": limit,
                            "offset": offset,
                            "stubbed": True,
                        },
                    )
                ],
            )

        # Stub mode is intentionally off below. Keep this for real upstream calls.
        # try:
        #     response = await self._client.get(
        #         "/search",
        #         params={
        #             "q": query,
        #             "limit": limit,
        #             "offset": offset,
        #         },
        #     )
        #     response.raise_for_status()
        # except httpx.TimeoutException as exc:
        #     raise APIError(
        #         status_code=504,
        #         code="search_timeout",
        #         detail="Search service request timed out.",
        #     ) from exc
        # except httpx.HTTPStatusError as exc:
        #     logger.warning("search_service_http_error status_code=%s", exc.response.status_code)
        #     raise APIError(
        #         status_code=502,
        #         code="search_upstream_error",
        #         detail="Search service returned an error.",
        #     ) from exc
        # except httpx.HTTPError as exc:
        #     raise APIError(
        #         status_code=502,
        #         code="search_unavailable",
        #         detail="Search service is unavailable.",
        #     ) from exc
        #
        # try:
        #     payload = response.json()
        # except ValueError as exc:
        #     raise APIError(
        #         status_code=502,
        #         code='search_invalid_payload',
        #         detail='Search service response payload is invalid.',
        #     ) from exc
        #
        # try:
        #     return SearchResponse.model_validate(payload)
        # except ValidationError as exc:
        #     raise APIError(
        #         status_code=502,
        #         code='search_invalid_payload',
        #         detail='Search service response payload is invalid.',
        #     ) from exc

        try:
            response = await self._client.get(
                "/search",
                params={
                    "q": query,
                    "limit": limit,
                    "offset": offset,
                },
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise APIError(
                status_code=504,
                code="search_timeout",
                detail="Search service request timed out.",
            ) from exc
        except httpx.HTTPStatusError as exc:
            logger.warning("search_service_http_error status_code=%s", exc.response.status_code)
            raise APIError(
                status_code=502,
                code="search_upstream_error",
                detail="Search service returned an error.",
            ) from exc
        except httpx.HTTPError as exc:
            raise APIError(
                status_code=502,
                code="search_unavailable",
                detail="Search service is unavailable.",
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise APIError(
                status_code=502,
                code="search_invalid_payload",
                detail="Search service response payload is invalid.",
            ) from exc

        try:
            return SearchResponse.model_validate(payload)
        except ValidationError as exc:
            raise APIError(
                status_code=502,
                code="search_invalid_payload",
                detail="Search service response payload is invalid.",
            ) from exc

    async def close(self) -> None:
        await self._client.aclose()

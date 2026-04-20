from fastapi.testclient import TestClient

from mismapi.core.errors import APIError
from mismapi.schemas.search import SearchResponse, SearchResultItem
from tests.conftest import build_test_app, container_of, override_principal


class FakeSearchClient:
    async def search(
        self,
        query: str,
        limit: int,
        offset: int,
    ) -> SearchResponse:
        assert query == "llm"
        assert limit == 10
        assert offset == 2
        return SearchResponse(
            total=1,
            results=[
                SearchResultItem(
                    data={
                        "name": "Example Model",
                        "description": "A test model",
                        "metadata": {"framework": "pytorch"},
                    },
                    score=0.91,
                )
            ],
        )

    async def close(self) -> None:
        return None


class FailingSearchClient:
    async def search(
        self,
        query: str,
        limit: int,
        offset: int,
    ) -> SearchResponse:
        raise APIError(status_code=502, code="search_upstream_error", detail="Upstream failed")

    async def close(self) -> None:
        return None


def test_search_success() -> None:
    with build_test_app({"AUTH_MODE": "jwt"}) as app:
        override_principal(app)
        with TestClient(app) as client:
            container_of(app).search_client = FakeSearchClient()  # type: ignore[assignment]
            response = client.get("/api/v1/models?q=llm&limit=10&offset=2")
            assert response.status_code == 200
            payload = response.json()
            assert payload["total"] == 1
            assert payload["results"][0]["data"]["name"] == "Example Model"


def test_search_upstream_error_translated() -> None:
    with build_test_app({"AUTH_MODE": "jwt"}) as app:
        override_principal(app)
        with TestClient(app) as client:
            container_of(app).search_client = FailingSearchClient()  # type: ignore[assignment]
            response = client.get("/api/v1/models?q=llm")
            assert response.status_code == 502
            payload = response.json()
            assert payload["error"]["code"] == "search_upstream_error"

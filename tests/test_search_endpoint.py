from fastapi.testclient import TestClient

from mism_api.auth.base import AuthenticatedPrincipal, require_principal
from mism_api.core.errors import APIError
from mism_api.main import create_app
from mism_api.schemas.search import SearchResponse, SearchResultItem


class FakeSearchClient:
    async def search(self, query: str, limit: int, offset: int) -> SearchResponse:
        assert query == "llm"
        assert limit == 10
        assert offset == 2
        return SearchResponse(
            total=1,
            results=[
                SearchResultItem(
                    id="model-1",
                    type="model",
                    name="Example Model",
                    description="A test model",
                    score=0.91,
                    metadata={"framework": "pytorch"},
                )
            ],
        )

    async def close(self) -> None:
        return None


class FailingSearchClient:
    async def search(self, query: str, limit: int, offset: int) -> SearchResponse:
        raise APIError(status_code=502, code="search_upstream_error", detail="Upstream failed")

    async def close(self) -> None:
        return None


async def allow_principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        subject="user-1",
        issuer="test",
        audience="mism-api",
        scopes=set(),
    )


def test_search_success() -> None:
    app = create_app()
    app.dependency_overrides[require_principal] = allow_principal
    with TestClient(app) as client:
        app.state.search_client = FakeSearchClient()
        response = client.get("/api/v1/models?q=llm&limit=10&offset=2")
        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 1
        assert payload["results"][0]["id"] == "model-1"


def test_search_upstream_error_translated() -> None:
    app = create_app()
    app.dependency_overrides[require_principal] = allow_principal
    with TestClient(app) as client:
        app.state.search_client = FailingSearchClient()
        response = client.get("/api/v1/models?q=llm")
        assert response.status_code == 502
        payload = response.json()
        assert payload["error"]["code"] == "search_upstream_error"

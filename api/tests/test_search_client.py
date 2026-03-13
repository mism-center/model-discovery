import httpx

from clients.search_client import SearchServiceClient


def _build_search_client_with_handler(handler: httpx.MockTransport) -> SearchServiceClient:
    client = SearchServiceClient(base_url="http://search-service", timeout_seconds=5.0)
    client._client = httpx.AsyncClient(
        transport=handler,
        base_url="http://search-service",
        timeout=5.0,
    )
    return client


async def test_search_accepts_mixed_metadata_value_types() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "total": 1,
                "results": [
                    {
                        "id": "model-1",
                        "type": "model",
                        "name": "Example",
                        "description": "Mixed metadata",
                        "score": 0.8,
                        "metadata": {
                            "framework": "pytorch",
                            "version": 3,
                            "quantized": False,
                            "threshold": 0.42,
                            "notes": None,
                        },
                    }
                ],
            },
        )

    client = _build_search_client_with_handler(httpx.MockTransport(handler))
    try:
        response = await client.search(query="example", limit=25, offset=0)
        assert response.total == 1
        assert response.results[0].metadata["version"] == 3
        assert response.results[0].metadata["quantized"] is False
        assert response.results[0].metadata["threshold"] == 0.42
        assert response.results[0].metadata["notes"] is None
    finally:
        await client.close()

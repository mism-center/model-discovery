import httpx

from mismapi.clients.search_client import SearchServiceClient


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
                        "data": {
                            "name": "Example",
                            "description": "Mixed metadata",
                            "metadata": {
                                "framework": "pytorch",
                                "version": 3,
                                "quantized": False,
                                "threshold": 0.42,
                                "notes": None,
                            },
                        },
                        "score": 0.8,
                    }
                ],
            },
        )

    client = _build_search_client_with_handler(httpx.MockTransport(handler))
    try:
        response = await client.search(
            query="example",
            limit=25,
            offset=0,
        )
        assert response.total == 1
        metadata = response.results[0].data["metadata"]
        assert isinstance(metadata, dict)
        assert metadata["version"] == 3
        assert metadata["quantized"] is False
        assert metadata["threshold"] == 0.42
        assert metadata["notes"] is None
    finally:
        await client.close()

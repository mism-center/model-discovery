import httpx
import respx

from mismapi.clients.search_client import SearchServiceClient

SEARCH_BASE_URL = "http://search-service"


@respx.mock
async def test_search_accepts_mixed_metadata_value_types() -> None:
    respx.get(f"{SEARCH_BASE_URL}/search").mock(
        return_value=httpx.Response(
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
    )

    client = SearchServiceClient(base_url=SEARCH_BASE_URL, timeout_seconds=5.0)
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

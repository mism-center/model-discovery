import httpx
import pytest
from fastapi.testclient import TestClient

from mismapi.clients.biomodels_client import BioModelsClient
from mismapi.clients.cairns_client import CairnsClient
from mismapi.core.deps import _get_biomodels_client, _get_cairns_client
from mismapi.core.errors import APIError
from mismapi.main import create_app
from mismapi.schemas.cairns import CairnsRecommendRequest
from tests.conftest import minimal_oidc_settings

_UPSTREAM_PAYLOAD = {
    "answer": "Here are 2 evidence-backed options.",
    "evidence": [
        {
            "tool_id": "biomodels_biomd0000000732",
            "name": "Kirschner1998_Immunotherapy_Tumour",
            "source": "biomodels",
            "score": 0.4674859,
            "snippet": "identifier: BIOMD0000000732",
            "why_matched": ["immune"],
            "url": "",
        },
        {"tool_id": "biotools_vcell", "name": "VCell", "source": "tooldb", "score": 0.44},
    ],
    "elapsed_seconds": 12.47,
}


def _client_with_transport(handler: httpx.MockTransport) -> CairnsClient:
    client = CairnsClient(base_url="http://cairns.test", timeout_seconds=5.0)
    client._client = httpx.AsyncClient(transport=handler, base_url="http://cairns.test")
    return client


def _make_app(
    cairns_client: CairnsClient,
    biomodels_client: BioModelsClient | None = None,
) -> TestClient:
    # Default to an unconfigured BioModels client so enrichment is a no-op and
    # these tests assert the proxy alone. See test_cairns_enrichment.py.
    biomodels = biomodels_client or BioModelsClient(base_url="")
    app = create_app(settings=minimal_oidc_settings())
    app.dependency_overrides[_get_cairns_client] = lambda: cairns_client
    app.dependency_overrides[_get_biomodels_client] = lambda: biomodels
    return TestClient(app)


# ── POST /cairns/recommend ─────────────────────────────────────


def test_recommend_proxies_upstream_payload() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = httpx.Response(200, content=request.content).json()
        return httpx.Response(200, json=_UPSTREAM_PAYLOAD)

    client = _make_app(_client_with_transport(httpx.MockTransport(handler)))
    response = client.post(
        "/api/v1/cairns/recommend",
        json={"question": "What can simulate T cell signaling?", "thread_id": "t-1"},
    )

    assert response.status_code == 200
    assert captured["url"] == "http://cairns.test/recommend"
    assert captured["body"] == {
        "question": "What can simulate T cell signaling?",
        "chat_history": [],
        "thread_id": "t-1",
    }

    payload = response.json()
    assert payload["answer"] == _UPSTREAM_PAYLOAD["answer"]
    assert payload["elapsed_seconds"] == 12.47
    assert [e["tool_id"] for e in payload["evidence"]] == [
        "biomodels_biomd0000000732",
        "biotools_vcell",
    ]
    assert payload["evidence"][0]["source"] == "biomodels"
    # Fields omitted upstream fall back to the schema defaults.
    assert payload["evidence"][1]["why_matched"] == []
    assert payload["evidence"][1]["snippet"] == ""


def test_recommend_forwards_chat_history() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = httpx.Response(200, content=request.content).json()
        return httpx.Response(200, json={"answer": "ok", "evidence": [], "elapsed_seconds": 0.1})

    client = _make_app(_client_with_transport(httpx.MockTransport(handler)))
    response = client.post(
        "/api/v1/cairns/recommend",
        json={"question": "And for mice?", "chat_history": [["q1", "a1"]]},
    )

    assert response.status_code == 200
    assert captured["body"] == {
        "question": "And for mice?",
        "chat_history": [["q1", "a1"]],
        "thread_id": None,
    }


def test_recommend_rejects_empty_question() -> None:
    client = _make_app(CairnsClient(base_url="http://cairns.test"))
    response = client.post("/api/v1/cairns/recommend", json={"question": ""})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"


def test_recommend_without_base_url_is_unavailable() -> None:
    client = _make_app(CairnsClient(base_url=""))
    response = client.post("/api/v1/cairns/recommend", json={"question": "anything"})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "cairns_not_configured"


def test_recommend_maps_upstream_server_error_to_502() -> None:
    handler = httpx.MockTransport(lambda _: httpx.Response(500, text="boom"))
    client = _make_app(_client_with_transport(handler))
    response = client.post("/api/v1/cairns/recommend", json={"question": "anything"})

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "cairns_recommend_failed"


def test_recommend_passes_through_upstream_client_error() -> None:
    handler = httpx.MockTransport(
        lambda _: httpx.Response(422, json={"detail": "question too long"})
    )
    client = _make_app(_client_with_transport(handler))
    response = client.post("/api/v1/cairns/recommend", json={"question": "anything"})

    assert response.status_code == 422
    assert response.json()["error"]["detail"] == "question too long"


def test_recommend_maps_timeout_to_504() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow", request=request)

    client = _make_app(_client_with_transport(httpx.MockTransport(handler)))
    response = client.post("/api/v1/cairns/recommend", json={"question": "anything"})

    assert response.status_code == 504
    assert response.json()["error"]["code"] == "cairns_recommend_timeout"


def test_recommend_rejects_unparseable_upstream_body() -> None:
    handler = httpx.MockTransport(lambda _: httpx.Response(200, text="not json"))
    client = _make_app(_client_with_transport(handler))
    response = client.post("/api/v1/cairns/recommend", json={"question": "anything"})

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "cairns_invalid_response"


def test_recommend_rejects_upstream_body_missing_answer() -> None:
    handler = httpx.MockTransport(lambda _: httpx.Response(200, json={"evidence": []}))
    client = _make_app(_client_with_transport(handler))
    response = client.post("/api/v1/cairns/recommend", json={"question": "anything"})

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "cairns_invalid_response"


async def test_client_raises_on_unreachable_host() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route", request=request)

    client = _client_with_transport(httpx.MockTransport(handler))
    with pytest.raises(APIError) as exc_info:
        await client.recommend(CairnsRecommendRequest(question="anything"))

    assert exc_info.value.status_code == 502
    assert exc_info.value.code == "cairns_recommend_failed"

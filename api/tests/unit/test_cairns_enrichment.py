import asyncio
import json
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from mismapi.clients.biomodels_client import BioModelsClient
from mismapi.clients.cairns_client import CairnsClient
from mismapi.core.deps import _get_biomodels_client, _get_cairns_client
from mismapi.core.errors import APIError
from mismapi.main import create_app
from mismapi.schemas.biomodels import normalize_model_id
from mismapi.schemas.cairns import CairnsEvidenceCardDTO
from tests.conftest import minimal_oidc_settings

# Trimmed from a live https://www.biomodels.org/BIOMD0000000732?format=json.
_CURATED_RECORD: dict[str, Any] = {
    "name": "Kirschner1998_Immunotherapy_Tumour",
    "description": '<notes xmlns="http://www.sbml.org/sbml/level2/version4"><body><p>x</p></body></notes>',
    "format": {"name": "SBML", "identifier": "SBML", "version": "L2V4"},
    "publication": {
        "type": "PubMed ID",
        "accession": "9785481",
        "journal": "Journal of mathematical biology",
        "title": "Modeling immunotherapy of the tumor-immune interaction.",
        "synopsis": "A number of lines of evidence suggest that immunotherapy...",
    },
    "files": {
        "main": [
            {
                "name": "Kirschner_1998.xml",
                "description": "SBML L2V4 representation",
                "fileSize": "43735",
                "mimeType": "application/xml",
                "md5sum": "6fc274441ab732233706200c0a8223da",
            }
        ],
        "additional": [{"name": "Kirschner_1998-biopax2.owl", "mimeType": "application/rdf+xml"}],
    },
    "firstPublished": 1725285431,
    "submissionId": "MODEL1006230038",
    "publicationId": "BIOMD0000000732",
    "modellingApproach": {
        "accession": "MAMO_0000046",
        "name": "ordinary differential equation model",
        "resource": "http://identifiers.org/mamo/MAMO_0000046",
    },
    "curationStatus": "CURATED",
    "contributors": {
        "Curator": [
            {
                "name": "Lucian Smith",
                "email": "lpsmith@uw.edu",
                "affiliation": "University of Washington",
                "orcid": "0000-0001-7002-6386",
            }
        ],
        "Modeller": [
            {"name": "Camille Laibe", "email": "laibe@ebi.ac.uk", "affiliation": "EMBL-EBI"}
        ],
    },
    "modelLevelAnnotations": [
        {
            "qualifier": "bqbiol:hasTaxon",
            "accession": "9606",
            "name": "Homo sapiens",
            "resource": "Taxonomy",
            "uri": "http://identifiers.org/taxonomy/9606",
        }
    ],
}

# Non-curated models carry no publicationId.
_NON_CURATED_RECORD: dict[str, Any] = {
    "name": "Cacace2020 - Logical model of T cell commitment",
    "description": "Boolean approaches and extensions thereof...",
    "format": {"name": "SBML", "identifier": "SBML", "version": "L3V1"},
    "submissionId": "MODEL2002170001",
    "curationStatus": "NON_CURATED",
    "firstPublished": 1617721020,
    "contributors": {"Modeller": [{"name": "Kirsten Cacace"}]},
}

_RECORDS_BY_MODEL_ID: dict[str, dict[str, Any]] = {
    "BIOMD0000000732": _CURATED_RECORD,
    "MODEL2002170001": _NON_CURATED_RECORD,
}


def _biomodels_handler(request: httpx.Request) -> httpx.Response:
    model_id = request.url.path.strip("/")
    record = _RECORDS_BY_MODEL_ID.get(model_id)
    if record is None:
        return httpx.Response(
            404, json={"resource": f"/{model_id}", "code": 404, "message": "Not Found"}
        )
    return httpx.Response(200, json=record)


def _biomodels_client(
    handler: httpx.MockTransport | None = None,
    *,
    base_url: str = "https://biomodels.test",
) -> BioModelsClient:
    client = BioModelsClient(base_url=base_url, timeout_seconds=5.0)
    client._client = httpx.AsyncClient(
        transport=handler or httpx.MockTransport(_biomodels_handler),
        base_url=base_url,
    )
    return client


def _card(tool_id: str, source: str, name: str = "n") -> CairnsEvidenceCardDTO:
    return CairnsEvidenceCardDTO(tool_id=tool_id, name=name, source=source)


# ── Accession parsing ──────────────────────────────────────────


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("BIOMD0000000732", "BIOMD0000000732"),
        ("biomd0000000732", "BIOMD0000000732"),
        ("  MODEL2002170001  ", "MODEL2002170001"),
        ("BMID000000000001", "BMID000000000001"),
        ("", None),
        ("BIOMD", None),
        ("0000000732", None),
        # Anything that could escape the request path must be rejected.
        ("../../admin", None),
        ("BIOMD0000000732/files", None),
        ("BIOMD0000000732?x=1", None),
        ("BIOMD0000000732,BIOMD0000000250", None),
    ],
)
def test_normalize_model_id(raw: str, expected: str | None) -> None:
    assert normalize_model_id(raw) == expected


@pytest.mark.parametrize(
    ("tool_id", "source", "expected"),
    [
        ("biomodels_biomd0000000732", "biomodels", "BIOMD0000000732"),
        ("biomodels_model2002170001", "biomodels", "MODEL2002170001"),
        ("BIOMD0000000732", "biomodels", "BIOMD0000000732"),
        ("biomodels_biomd0000000732", "BioModels", "BIOMD0000000732"),
        # tooldb cards are left alone, even if the id would parse.
        ("biomodels_biomd0000000732", "tooldb", None),
        ("biotools_vcell", "tooldb", None),
        ("biomodels_", "biomodels", None),
    ],
)
def test_card_biomodels_model_id(tool_id: str, source: str, expected: str | None) -> None:
    assert _card(tool_id, source).biomodels_model_id == expected


# ── Client ─────────────────────────────────────────────────────


async def test_get_model_maps_upstream_record() -> None:
    record = await _biomodels_client().get_model("biomd0000000732")

    assert record.identifier == "BIOMD0000000732"
    assert record.url == "https://biomodels.test/BIOMD0000000732"
    assert record.name == "Kirschner1998_Immunotherapy_Tumour"
    assert record.curation_status == "CURATED"
    assert record.submission_id == "MODEL1006230038"
    assert record.publication_id == "BIOMD0000000732"
    assert record.format is not None and record.format.version == "L2V4"
    assert record.modelling_approach is not None
    assert record.modelling_approach.name == "ordinary differential equation model"
    assert record.publication is not None
    assert record.publication.accession == "9785481"
    assert record.publication.journal == "Journal of mathematical biology"
    assert record.first_published is not None
    assert record.first_published.year == 2024
    assert [a.name for a in record.annotations] == ["Homo sapiens"]
    assert record.annotations[0].qualifier == "bqbiol:hasTaxon"
    assert record.files is not None
    assert record.files.main[0].name == "Kirschner_1998.xml"
    # fileSize arrives as a string upstream.
    assert record.files.main[0].file_size == 43735
    assert record.files.main[0].mime_type == "application/xml"
    assert [f.name for f in record.files.additional] == ["Kirschner_1998-biopax2.owl"]


async def test_get_model_flattens_contributors_and_drops_emails() -> None:
    record = await _biomodels_client().get_model("BIOMD0000000732")

    assert [(c.name, c.role) for c in record.contributors] == [
        ("Lucian Smith", "Curator"),
        ("Camille Laibe", "Modeller"),
    ]
    assert record.contributors[0].orcid == "0000-0001-7002-6386"
    assert record.contributors[0].affiliation == "University of Washington"
    serialized = json.dumps(record.model_dump(mode="json"))
    assert "lpsmith@uw.edu" not in serialized
    assert "email" not in serialized


async def test_get_model_omits_raw_sbml_notes_description() -> None:
    record = await _biomodels_client().get_model("BIOMD0000000732")

    serialized = json.dumps(record.model_dump(mode="json"))
    assert "<notes" not in serialized
    assert not hasattr(record, "description")


async def test_get_model_handles_non_curated_record() -> None:
    record = await _biomodels_client().get_model("MODEL2002170001")

    assert record.identifier == "MODEL2002170001"
    assert record.curation_status == "NON_CURATED"
    assert record.publication_id == ""
    assert record.publication is None
    assert record.files is None
    assert record.annotations == []


async def test_get_model_rejects_non_model_id_without_calling_upstream() -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError(f"upstream must not be called, got {request.url}")

    client = _biomodels_client(httpx.MockTransport(handler))
    with pytest.raises(APIError) as exc_info:
        await client.get_model("../../etc/passwd")

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "biomodels_invalid_model_id"


async def test_get_model_rejects_html_body_served_with_200() -> None:
    handler = httpx.MockTransport(
        lambda _: httpx.Response(200, text="<!doctype html><html></html>")
    )
    with pytest.raises(APIError) as exc_info:
        await _biomodels_client(handler).get_model("BIOMD0000000732")

    assert exc_info.value.status_code == 502
    assert exc_info.value.code == "biomodels_invalid_response"


async def test_get_model_unconfigured_is_unavailable() -> None:
    with pytest.raises(APIError) as exc_info:
        await BioModelsClient(base_url="").get_model("BIOMD0000000732")

    assert exc_info.value.status_code == 503
    assert exc_info.value.code == "biomodels_not_configured"


async def test_get_models_dedupes_and_skips_failures() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path.strip("/"))
        return _biomodels_handler(request)

    records = await _biomodels_client(httpx.MockTransport(handler)).get_models(
        [
            "BIOMD0000000732",
            "biomd0000000732",
            "MODEL2002170001",
            "BIOMD0000000404",
            "not-a-model-id",
        ]
    )

    assert sorted(records) == ["BIOMD0000000732", "MODEL2002170001"]
    assert sorted(seen) == ["BIOMD0000000404", "BIOMD0000000732", "MODEL2002170001"]


async def test_get_models_respects_concurrency_cap() -> None:
    in_flight = 0
    peak = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        # Hold the request open so overlapping ones pile up if the cap is gone.
        await asyncio.sleep(0.02)
        in_flight -= 1
        return httpx.Response(200, json=_NON_CURATED_RECORD)

    client = BioModelsClient(
        base_url="https://biomodels.test", timeout_seconds=5.0, max_concurrency=3
    )
    client._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://biomodels.test"
    )

    model_ids = [f"BIOMD{i:010d}" for i in range(12)]
    records = await client.get_models(model_ids)

    assert len(records) == 12
    assert peak == 3


async def test_get_models_returns_empty_when_unconfigured() -> None:
    assert await BioModelsClient(base_url="").get_models(["BIOMD0000000732"]) == {}


# ── Through the endpoint ───────────────────────────────────────


def _cairns_client_returning(payload: dict[str, Any]) -> CairnsClient:
    client = CairnsClient(base_url="http://cairns.test", timeout_seconds=5.0)
    client._client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload)),
        base_url="http://cairns.test",
    )
    return client


def _recommend(
    evidence: list[dict[str, Any]],
    biomodels: BioModelsClient | None = None,
    *,
    answer: str = "Here are your options.",
) -> dict[str, Any]:
    """POST /cairns/recommend behind a stubbed CAIRNS, and return the body."""
    payload = {"answer": answer, "evidence": evidence, "elapsed_seconds": 12.47}
    resolved = biomodels if biomodels is not None else _biomodels_client()

    app = create_app(settings=minimal_oidc_settings())
    app.dependency_overrides[_get_cairns_client] = lambda: _cairns_client_returning(payload)
    app.dependency_overrides[_get_biomodels_client] = lambda: resolved

    response = TestClient(app).post("/api/v1/cairns/recommend", json={"question": "q"})
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    return body


def test_endpoint_resolves_full_record_onto_biomodels_card() -> None:
    body = _recommend(
        [
            {
                "tool_id": "biomodels_biomd0000000732",
                "name": "Kirschner1998_Immunotherapy_Tumour",
                "source": "biomodels",
                "score": 0.46,
                "snippet": "identifier: BIOMD0000000732",
            }
        ]
    )

    biomodels = body["evidence"][0]["biomodels"]
    assert biomodels["identifier"] == "BIOMD0000000732"
    assert biomodels["url"] == "https://biomodels.test/BIOMD0000000732"
    assert biomodels["curation_status"] == "CURATED"
    assert biomodels["publication"]["title"] == (
        "Modeling immunotherapy of the tumor-immune interaction."
    )
    assert biomodels["modelling_approach"]["name"] == "ordinary differential equation model"
    assert biomodels["annotations"][0]["name"] == "Homo sapiens"
    assert biomodels["files"]["main"][0]["file_size"] == 43735
    # Emitted snake_case, not upstream's camelCase.
    assert "curationStatus" not in biomodels
    assert "modelLevelAnnotations" not in biomodels


def test_endpoint_resolves_biomodels_cards_only() -> None:
    body = _recommend(
        [
            {
                "tool_id": "biomodels_biomd0000000732",
                "name": "Kirschner1998",
                "source": "biomodels",
            },
            {"tool_id": "biotools_vcell", "name": "VCell", "source": "tooldb"},
            {"tool_id": "biomodels_model2002170001", "name": "Cacace2020", "source": "biomodels"},
        ]
    )

    first, second, third = body["evidence"]
    assert first["biomodels"]["identifier"] == "BIOMD0000000732"
    assert second["biomodels"] is None
    assert third["biomodels"]["identifier"] == "MODEL2002170001"
    # CAIRNS' own fields survive untouched.
    assert [c["name"] for c in body["evidence"]] == ["Kirschner1998", "VCell", "Cacace2020"]


def test_endpoint_leaves_unknown_model_id_null() -> None:
    body = _recommend(
        [{"tool_id": "biomodels_biomd0000000404", "name": "gone", "source": "biomodels"}]
    )

    assert body["evidence"][0]["biomodels"] is None


def test_endpoint_skips_biomodels_when_no_card_needs_it() -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError(f"BioModels must not be called, got {request.url}")

    body = _recommend(
        [{"tool_id": "biotools_vcell", "name": "VCell", "source": "tooldb"}],
        _biomodels_client(httpx.MockTransport(handler)),
    )

    assert body["evidence"][0]["biomodels"] is None


def test_endpoint_still_answers_when_biomodels_is_down() -> None:
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    body = _recommend(
        [
            {
                "tool_id": "biomodels_biomd0000000732",
                "name": "Kirschner1998",
                "source": "biomodels",
            }
        ],
        _biomodels_client(httpx.MockTransport(down)),
        answer="Here is 1 option.",
    )

    assert body["answer"] == "Here is 1 option."
    assert body["evidence"][0]["name"] == "Kirschner1998"
    assert body["evidence"][0]["biomodels"] is None


def test_endpoint_still_answers_when_biomodels_is_unconfigured() -> None:
    body = _recommend(
        [
            {
                "tool_id": "biomodels_biomd0000000732",
                "name": "Kirschner1998",
                "source": "biomodels",
            }
        ],
        BioModelsClient(base_url=""),
    )

    assert body["evidence"][0]["biomodels"] is None

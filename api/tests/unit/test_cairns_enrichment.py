from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient
from mism_registry.enums import ResourceRegistrationStatus, ResourceType
from mism_registry.in_memory import InMemoryRegistry
from mism_registry.resource import Resource

from mismapi.auth.principal import AuthenticatedPrincipal
from mismapi.clients.biomodels_client import BioModelsClient
from mismapi.clients.cairns_client import CairnsClient
from mismapi.core.deps import _get_cairns_client, _get_registry_service
from mismapi.core.errors import APIError
from mismapi.main import create_app
from mismapi.schemas.biomodels import normalize_model_id
from mismapi.services.registry_service import RegistryService
from tests.conftest import minimal_oidc_settings, override_anonymous, override_principal

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
        "affiliation": "Department of Mathematics, Tulane University",
        "synopsis": "A number of lines of evidence suggest that immunotherapy...",
        # `year` is an int and `month` a string in the same upstream record.
        "year": 1998,
        "month": "7",
        "volume": "37",
        "issue": "3",
        "pages": "235-52",
        "link": "http://identifiers.org/pubmed/9785481",
        "authors": [
            {"name": "D Kirschner", "institution": "Department of Mathematics"},
            {"name": "J C Panetta"},
        ],
    },
    "files": {
        "main": [
            {
                "name": "Kirschner_1998.xml",
                "description": "SBML L2V4 representation",
                "fileSize": "43735",
                "mimeType": "application/xml",
                "md5sum": "6fc274441ab732233706200c0a8223da",
                "sha1sum": "1bd00d4efaa4279e96a4420d40578ef85ad9bb45",
                "sha256sum": "e4738f53e1941d6d2bce0c37de6ce6493567ac39f6a0dfb0e9845e6c470b1ff0",
            }
        ],
        "additional": [{"name": "Kirschner_1998-biopax2.owl", "mimeType": "application/rdf+xml"}],
    },
    "history": {
        "revisions": [
            {
                "version": 1,
                "submitted": 1277287200,
                "submitter": "Camille Laibe",
                "comment": "Original import of Kirschner1998_Immunotherapy_Tumour",
            },
            {
                "version": 2,
                "submitted": 1724285866,
                "submitter": "Lucian Smith",
                "comment": "CRBM-sponsored manual and automated updates.",
            },
        ]
    },
    "firstPublished": 1725285431,
    "submissionId": "MODEL1006230038",
    "publicationId": "BIOMD0000000732",
    "vcsIdentifier": "aaa",
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
                "external": False,
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


def _key_paths(node: Any, prefix: str = "") -> set[str]:
    """Every dotted key path in `node`, merging list entries so sparse ones count."""
    if isinstance(node, dict):
        return {
            path
            for key, value in node.items()
            for path in {f"{prefix}{key}", *_key_paths(value, f"{prefix}{key}.")}
        }
    if isinstance(node, list):
        return {path for entry in node for path in _key_paths(entry, prefix)}
    return set()


async def test_get_model_drops_no_upstream_field() -> None:
    """The record is written verbatim to the annotation manifest, so a field the
    DTO fails to declare is data the agent silently never sees."""
    record = await _biomodels_client().get_model("BIOMD0000000732")

    emitted = {p.replace("_", "").lower() for p in _key_paths(record.model_dump(mode="json"))}
    # The two shapes the DTO deliberately normalizes: annotations are renamed,
    # and contributors are flattened out of their per-role map.
    upstream = {
        p.replace("modelLevelAnnotations", "annotations")
        .replace("contributors.Curator", "contributors")
        .replace("contributors.Modeller", "contributors")
        .replace("_", "")
        .lower()
        for p in _key_paths(_CURATED_RECORD)
    }

    assert not upstream - emitted


async def test_get_model_maps_the_full_citation() -> None:
    record = await _biomodels_client().get_model("BIOMD0000000732")

    assert record.publication is not None
    publication = record.publication
    assert publication.year == 1998
    assert publication.month == "7"
    assert publication.volume == "37"
    assert publication.issue == "3"
    assert publication.pages == "235-52"
    assert publication.link == "http://identifiers.org/pubmed/9785481"
    assert publication.affiliation == "Department of Mathematics, Tulane University"
    assert [(a.name, a.institution) for a in publication.authors] == [
        ("D Kirschner", "Department of Mathematics"),
        ("J C Panetta", ""),
    ]


async def test_get_model_maps_history_and_checksums() -> None:
    record = await _biomodels_client().get_model("BIOMD0000000732")

    assert record.vcs_identifier == "aaa"
    assert record.history is not None
    assert [r.version for r in record.history.revisions] == [1, 2]
    assert record.history.revisions[0].submitter == "Camille Laibe"
    assert record.history.revisions[1].submitted is not None
    assert record.history.revisions[1].submitted.year == 2024
    assert record.files is not None
    assert record.files.main[0].sha256sum == (
        "e4738f53e1941d6d2bce0c37de6ce6493567ac39f6a0dfb0e9845e6c470b1ff0"
    )
    assert record.files.main[0].sha1sum == "1bd00d4efaa4279e96a4420d40578ef85ad9bb45"


async def test_get_model_flattens_contributors_and_keeps_emails() -> None:
    record = await _biomodels_client().get_model("BIOMD0000000732")

    assert [(c.name, c.role) for c in record.contributors] == [
        ("Lucian Smith", "Curator"),
        ("Camille Laibe", "Modeller"),
    ]
    assert record.contributors[0].orcid == "0000-0001-7002-6386"
    assert record.contributors[0].affiliation == "University of Washington"
    assert record.contributors[0].email == "lpsmith@uw.edu"


async def test_get_model_keeps_the_raw_sbml_notes_description() -> None:
    """Upstream XHTML, passed through unaltered — consumers must not render it as HTML."""
    record = await _biomodels_client().get_model("BIOMD0000000732")

    assert record.description.startswith("<notes")


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


# ── Through the endpoint ───────────────────────────────────────


def _cairns_client_returning(payload: dict[str, Any]) -> CairnsClient:
    client = CairnsClient(base_url="http://cairns.test", timeout_seconds=5.0)
    client._client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload)),
        base_url="http://cairns.test",
    )
    return client


def _principal(subject: str) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(subject=subject, issuer="test", audience="mism-api", scopes=set())


def _imported_resource(
    model_id: str, *, mism_id: str, owner: str, approved: bool = False
) -> Resource:
    return Resource(
        id=mism_id,
        name=f"Import of {model_id}",
        resource_type=ResourceType.MODEL,
        location_uri=f"irods:///{mism_id}/0.0.1",
        registration_status=(
            ResourceRegistrationStatus.APPROVED if approved else ResourceRegistrationStatus.DRAFT
        ),
        owner=owner,
        source_repository="biomodels",
        source_identifier=model_id,
    )


def _native_resource(mism_id: str, *, owner: str, approved: bool = False) -> Resource:
    return Resource(
        id=mism_id,
        name=f"Model {mism_id}",
        resource_type=ResourceType.MODEL,
        location_uri=f"irods:///{mism_id}/0.0.1",
        registration_status=(
            ResourceRegistrationStatus.APPROVED if approved else ResourceRegistrationStatus.DRAFT
        ),
        owner=owner,
    )


def _registry_holding(*resources: Resource) -> RegistryService:
    registry = InMemoryRegistry()
    for resource in resources:
        registry.register_resource(resource)
    return RegistryService(registry=registry, session=MagicMock())


def _recommend(
    evidence: list[dict[str, Any]],
    *,
    answer: str = "Here are your options.",
    registry: Any = None,
    principal: AuthenticatedPrincipal | None = None,
) -> dict[str, Any]:
    """POST /cairns/recommend behind a stubbed CAIRNS, and return the body.

    Defaults to an anonymous caller. The auth overrides are not optional: the
    endpoint takes ``OptionalPrincipalDep``, and this client never runs lifespan,
    so the real dependency would fail on the missing container.
    """
    payload = {"answer": answer, "evidence": evidence, "elapsed_seconds": 12.47}

    app = create_app(settings=minimal_oidc_settings())
    app.dependency_overrides[_get_cairns_client] = lambda: _cairns_client_returning(payload)
    app.dependency_overrides[_get_registry_service] = lambda: (
        registry if registry is not None else _registry_holding()
    )
    if principal is None:
        override_anonymous(app)
    else:
        override_principal(app, principal)

    response = TestClient(app).post("/api/v1/cairns/recommend", json={"question": "q"})
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    return body


# ── Registry cross-reference: BioModels cards ──────────────────


_BIOMODELS_CARD = {
    "tool_id": "biomodels_biomd0000000732",
    "name": "Kirschner1998",
    "source": "biomodels",
    "metadata": {"identifier": "BIOMD0000000732"},
}


def test_approved_import_is_cross_referenced_for_anonymous_callers() -> None:
    registry = _registry_holding(
        _imported_resource("BIOMD0000000732", mism_id="m-1", owner="user-1", approved=True)
    )

    body = _recommend([_BIOMODELS_CARD], registry=registry)

    assert body["evidence"][0]["mism_model_id"] == "m-1"


def test_another_users_unapproved_import_is_not_cross_referenced() -> None:
    """It would leak the existence and id of a draft the caller cannot open."""
    registry = _registry_holding(
        _imported_resource("BIOMD0000000732", mism_id="m-1", owner="user-2")
    )

    body = _recommend([_BIOMODELS_CARD], registry=registry, principal=_principal("user-1"))

    assert body["evidence"][0]["mism_model_id"] is None


def test_own_unapproved_import_is_cross_referenced() -> None:
    registry = _registry_holding(
        _imported_resource("BIOMD0000000732", mism_id="m-1", owner="user-1")
    )

    body = _recommend([_BIOMODELS_CARD], registry=registry, principal=_principal("user-1"))

    assert body["evidence"][0]["mism_model_id"] == "m-1"


def test_approved_copy_wins_over_the_callers_own_draft() -> None:
    # Approved registered first, so insertion order alone would pick the draft.
    registry = _registry_holding(
        _imported_resource("BIOMD0000000732", mism_id="approved", owner="user-2", approved=True),
        _imported_resource("BIOMD0000000732", mism_id="mine", owner="user-1"),
    )

    body = _recommend([_BIOMODELS_CARD], registry=registry, principal=_principal("user-1"))

    assert body["evidence"][0]["mism_model_id"] == "approved"


def test_uncatalogued_model_leaves_the_cross_reference_null() -> None:
    body = _recommend([_BIOMODELS_CARD])

    assert body["evidence"][0]["mism_model_id"] is None


# ── Registry cross-reference: MISM cards ───────────────────────


_MISM_ID = "d0d9a71d-d801-4232-b040-c7164fa7810b"

_MISM_CARD = {
    "tool_id": f"mism_{_MISM_ID}",
    "name": "Kirschner1998_Immunotherapy_Tumour",
    "source": "MISM_models",
    "metadata": {
        "identifier": _MISM_ID,
        "url": f"https://mism-dev.renci.org/api/v1/models/{_MISM_ID}",
        "raw_metadata": {
            "id": _MISM_ID,
            "name": "Kirschner1998_Immunotherapy_Tumour",
            "resource_type": "model",
            "location_uri": f"{_MISM_ID}/0.0.1",
            "status": "active",
            "registration_status": "approved",
            "organisms": ["Homo sapiens"],
            "created_at": "2026-09-10T16:50:41.756357Z",
            "updated_at": "2026-09-10T16:54:50.807903Z",
        },
    },
}


def test_mism_card_links_to_the_approved_model_it_names() -> None:
    registry = _registry_holding(_native_resource(_MISM_ID, owner="user-1", approved=True))

    body = _recommend([_MISM_CARD], registry=registry)

    assert body["evidence"][0]["mism_model_id"] == _MISM_ID


def test_mism_card_for_a_model_this_registry_lacks_is_not_linked() -> None:
    """CAIRNS may index another deployment's registry, or a stale snapshot of this one."""
    body = _recommend([_MISM_CARD])

    assert body["evidence"][0]["mism_model_id"] is None


def test_mism_card_for_another_users_unapproved_model_is_not_linked() -> None:
    registry = _registry_holding(_native_resource(_MISM_ID, owner="user-2"))

    body = _recommend([_MISM_CARD], registry=registry, principal=_principal("user-1"))

    assert body["evidence"][0]["mism_model_id"] is None


def test_mism_card_for_own_unapproved_model_is_linked() -> None:
    registry = _registry_holding(_native_resource(_MISM_ID, owner="user-1"))

    body = _recommend([_MISM_CARD], registry=registry, principal=_principal("user-1"))

    assert body["evidence"][0]["mism_model_id"] == _MISM_ID


def test_cards_of_every_source_are_linked_side_by_side() -> None:
    registry = _registry_holding(
        _native_resource(_MISM_ID, owner="user-1", approved=True),
        _imported_resource("BIOMD0000000732", mism_id="m-1", owner="user-1", approved=True),
    )

    body = _recommend(
        [
            _MISM_CARD,
            {"tool_id": "biotools_vcell", "name": "VCell", "source": "tooldb"},
            _BIOMODELS_CARD,
        ],
        registry=registry,
    )

    assert [c["mism_model_id"] for c in body["evidence"]] == [_MISM_ID, None, "m-1"]
    raw = body["evidence"][0]["metadata"]["raw_metadata"]
    assert raw["id"] == _MISM_ID
    assert raw["organisms"] == ["Homo sapiens"]
    assert [c["name"] for c in body["evidence"]] == [
        "Kirschner1998_Immunotherapy_Tumour",
        "VCell",
        "Kirschner1998",
    ]


def test_registry_outage_still_answers_without_links() -> None:
    registry = MagicMock(spec=RegistryService)
    registry.get_model.side_effect = RuntimeError("registry down")
    registry.find_by_source.side_effect = RuntimeError("registry down")

    body = _recommend([_MISM_CARD, _BIOMODELS_CARD], registry=registry, answer="Here is 1 option.")

    assert body["answer"] == "Here is 1 option."
    assert [c["mism_model_id"] for c in body["evidence"]] == [None, None]

from urllib.parse import parse_qs, urlparse

from mismapi.auth.return_to import DEFAULT_LANDING_PATH, resolve_return_to


def test_known_key_without_query_maps_to_path() -> None:
    assert resolve_return_to("search", None) == "/search"


def test_runs_key_maps_to_path() -> None:
    # Auth-gated /runs route round-trips back after login.
    assert resolve_return_to("runs", None) == "/runs"


def test_known_key_reattaches_query() -> None:
    result = resolve_return_to("search", "q=foo&filter=bar")
    parsed = urlparse(result)
    assert parsed.path == "/search"
    assert parse_qs(parsed.query) == {"q": ["foo"], "filter": ["bar"]}


def test_unknown_key_falls_back_to_default() -> None:
    assert resolve_return_to("admin", "q=foo") == DEFAULT_LANDING_PATH


def test_missing_key_falls_back_to_default() -> None:
    assert resolve_return_to(None, "q=foo") == DEFAULT_LANDING_PATH
    assert resolve_return_to("", None) == DEFAULT_LANDING_PATH


def test_query_is_treated_as_data_not_a_url() -> None:
    # A would-be open redirect smuggled through the query string stays a query
    # value on the server-controlled /search path; it cannot change the origin.
    result = resolve_return_to("search", "next=https://evil.example.com")
    parsed = urlparse(result)
    assert parsed.path == "/search"
    assert parsed.netloc == ""
    assert parse_qs(parsed.query) == {"next": ["https://evil.example.com"]}


# ── Parameterized routes (`/models/{id}`) ────────────────────────────


VALID_ID = "cdb69007-99a9-4fd4-8705-72c7bcd5fbd1"


def test_model_key_with_valid_uuid_maps_to_detail_path() -> None:
    assert resolve_return_to("model", None, VALID_ID) == f"/models/{VALID_ID}"


def test_model_key_reattaches_query() -> None:
    result = resolve_return_to("model", "tab=files", VALID_ID)
    parsed = urlparse(result)
    assert parsed.path == f"/models/{VALID_ID}"
    assert parse_qs(parsed.query) == {"tab": ["files"]}


def test_model_key_without_id_falls_back_to_default() -> None:
    assert resolve_return_to("model", None, None) == DEFAULT_LANDING_PATH
    assert resolve_return_to("model", None, "") == DEFAULT_LANDING_PATH


def test_static_key_ignores_a_supplied_id() -> None:
    # `search` is not parameterized; an id must not be able to graft a segment on.
    assert resolve_return_to("search", None, VALID_ID) == "/search"


def test_non_uuid_ids_are_rejected() -> None:
    """The id is parsed as a UUID, so nothing that is not exactly a UUID gets in.

    Covers the shapes an attacker would reach for to escape the template: path
    traversal, an extra segment, a protocol-relative host, an absolute URL, and a
    newline for header smuggling.
    """
    for hostile in (
        "../../evil",
        f"{VALID_ID}/../../evil",
        f"{VALID_ID}/extra",
        "//evil.example.com",
        "https://evil.example.com",
        "http:/evil.example.com",
        f"{VALID_ID}\nLocation: https://evil.example.com",
        f"{VALID_ID}?next=https://evil.example.com",
        "not-a-uuid",
    ):
        assert resolve_return_to("model", None, hostile) == DEFAULT_LANDING_PATH, hostile


def test_resolved_model_path_never_changes_origin() -> None:
    parsed = urlparse(resolve_return_to("model", None, VALID_ID))
    assert parsed.scheme == ""
    assert parsed.netloc == ""
    assert parsed.path.startswith("/models/")

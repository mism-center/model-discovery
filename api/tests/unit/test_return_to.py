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

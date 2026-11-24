from urllib.parse import parse_qs, urlparse

import pytest

from mismapi.utils import merge_query_params


def test_absolute_url_without_query() -> None:
    result = merge_query_params("https://app.example.com/home", {"a": "1"})
    assert result == "https://app.example.com/home?a=1"


def test_relative_path_without_query() -> None:
    result = merge_query_params("/api/auth/login", {"a": "1"})
    assert result == "/api/auth/login?a=1"


def test_existing_query_params_are_preserved() -> None:
    result = merge_query_params("https://app.example.com/home?lang=en", {"a": "1"})
    parsed = urlparse(result)
    assert parse_qs(parsed.query) == {"lang": ["en"], "a": ["1"]}


def test_fragment_is_preserved_and_query_comes_before_it() -> None:
    """Hash-routed SPA URIs: query must be inserted before the fragment."""
    result = merge_query_params("https://app.example.com/#/home", {"a": "1"})
    parsed = urlparse(result)
    assert parsed.fragment == "/home"
    assert parse_qs(parsed.query) == {"a": ["1"]}
    assert result == "https://app.example.com/?a=1#/home"


def test_fragment_and_existing_query_both_preserved() -> None:
    result = merge_query_params(
        "https://app.example.com/home?utm=x#section-2",
        {"a": "1"},
    )
    parsed = urlparse(result)
    assert parsed.fragment == "section-2"
    assert parse_qs(parsed.query) == {"utm": ["x"], "a": ["1"]}


def test_trailing_question_mark_does_not_produce_double_separator() -> None:
    result = merge_query_params("https://app.example.com/home?", {"a": "1"})
    assert "?&" not in result
    assert result == "https://app.example.com/home?a=1"


def test_reserved_characters_are_percent_encoded() -> None:
    result = merge_query_params(
        "https://app.example.com/",
        {"msg": "100% denied: & #done"},
    )
    parsed = urlparse(result)
    assert parse_qs(parsed.query) == {"msg": ["100% denied: & #done"]}


def test_empty_extra_leaves_query_unchanged_semantically() -> None:
    result = merge_query_params("https://app.example.com/home?lang=en", {})
    parsed = urlparse(result)
    assert parse_qs(parsed.query) == {"lang": ["en"]}


def test_blank_valued_existing_param_is_preserved() -> None:
    result = merge_query_params("https://app.example.com/home?flag=", {"a": "1"})
    parsed = urlparse(result)
    assert parsed.query.split("&")[0] == "flag="
    assert parse_qs(parsed.query, keep_blank_values=True) == {"flag": [""], "a": ["1"]}


@pytest.mark.parametrize(
    ("url", "extra", "expected_query_keys"),
    [
        ("", {"a": "1"}, {"a"}),
        ("https://app.example.com", {"a": "1", "b": "2"}, {"a", "b"}),
    ],
)
def test_edge_cases(url: str, extra: dict[str, str], expected_query_keys: set[str]) -> None:
    result = merge_query_params(url, extra)
    parsed = urlparse(result)
    assert set(parse_qs(parsed.query).keys()) == expected_query_keys

import pytest

from mismapi.utils import get_string_or_empty_from_dict


@pytest.mark.parametrize(
    ("data", "key", "expected"),
    [
        ({}, "a", ""),
        ({"a": "x"}, "a", "x"),
        ({"a": ""}, "a", ""),
        ({"a": None}, "a", ""),
        ({"a": 1}, "a", ""),
    ],
)
def test_get_string_or_empty_from_dict(data: dict[str, object], key: str, expected: str) -> None:
    assert get_string_or_empty_from_dict(data, key) == expected

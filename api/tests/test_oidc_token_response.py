import pytest

from mismapi.auth.oidc import _build_authlib_token_response, _coerce_expires_in
from mismapi.core.errors import APIError


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (0, 0),
        (3600, 3600),
        (3600.9, 3600),
        ("7200", 7200),
        ("  90  ", 90),
        ("", 0),
        ("not-a-number", 0),
        (True, 0),
        (False, 0),
        (-1, 0),
        ("-5", 0),
        (None, 0),
        ([], 0),
    ],
)
def test_coerce_expires_in(raw: object, expected: int) -> None:
    assert _coerce_expires_in(raw) == expected


def test_coerce_expires_in_nan_float() -> None:
    assert _coerce_expires_in(float("nan")) == 0


def test_coerce_expires_in_inf_float() -> None:
    assert _coerce_expires_in(float("inf")) == 0


def test_build_authlib_token_response_minimal() -> None:
    tr = _build_authlib_token_response({"access_token": "at"})
    assert tr.access_token == "at"
    assert tr.refresh_token == ""
    assert tr.id_token == ""
    assert tr.expires_in == 0


def test_build_authlib_token_response_rejects_blank_access_token() -> None:
    with pytest.raises(APIError) as excinfo:
        _build_authlib_token_response({"access_token": "   "})
    assert excinfo.value.code == "auth_token_exchange_invalid"


def test_build_authlib_token_response_refresh_error_code() -> None:
    with pytest.raises(APIError) as excinfo:
        _build_authlib_token_response(
            {"access_token": ""},
            invalid_access_token_code="auth_token_refresh_invalid",
        )
    assert excinfo.value.code == "auth_token_refresh_invalid"


def test_build_authlib_token_response_non_string_access_token() -> None:
    with pytest.raises(APIError) as excinfo:
        _build_authlib_token_response({"access_token": 123})
    assert excinfo.value.code == "auth_token_exchange_invalid"

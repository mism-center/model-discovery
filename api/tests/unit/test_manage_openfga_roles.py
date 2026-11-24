"""Unit tests for the mism-manage-openfga-roles admin CLI (MISM-291).

OpenFGA has no built-in admin UI, so this script is the only way to grant or
revoke the four platform-wide roles. Tests exercise argument parsing and the
grant/revoke dispatch, with the OpenFGAClient mocked — no live OpenFGA needed.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from mismapi.cli.manage_openfga_roles import (
    PLATFORM_OBJECT,
    VALID_ROLES,
    build_parser,
    main,
)
from mismapi.clients.openfga_client import OpenFGAClient
from mismapi.core.errors import APIError

# ── Argument parsing ─────────────────────────────────────────────────


def test_grant_parses_role_and_user() -> None:
    args = build_parser().parse_args(["grant", "--role", "uploader", "--user", "alice"])
    assert args.action == "grant"
    assert args.role == "uploader"
    assert args.user == "alice"


def test_revoke_parses_role_and_user() -> None:
    args = build_parser().parse_args(["revoke", "--role", "executor", "--user", "bob"])
    assert args.action == "revoke"
    assert args.role == "executor"
    assert args.user == "bob"


def test_invalid_role_rejected() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["grant", "--role", "bogus", "--user", "alice"])


def test_missing_action_rejected() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["--role", "uploader", "--user", "alice"])


def test_all_four_platform_roles_accepted() -> None:
    for role in VALID_ROLES:
        args = build_parser().parse_args(["grant", "--role", role, "--user", "alice"])
        assert args.role == role


# ── grant / revoke dispatch ──────────────────────────────────────────


def _mock_client() -> AsyncMock:
    client = AsyncMock(spec=OpenFGAClient)
    return client


def test_main_grant_calls_write_tuple(capsys: pytest.CaptureFixture[str]) -> None:
    client = _mock_client()
    with patch("mismapi.cli.manage_openfga_roles.OpenFGAClient", return_value=client):
        exit_code = main(["grant", "--role", "uploader", "--user", "alice"])

    assert exit_code == 0
    client.write_tuple.assert_awaited_once_with(
        user="user:alice", relation="uploader", object_=PLATFORM_OBJECT
    )
    client.delete_tuple.assert_not_awaited()
    client.close.assert_awaited_once()
    assert "Granted 'uploader' to user:alice" in capsys.readouterr().out


def test_main_revoke_calls_delete_tuple(capsys: pytest.CaptureFixture[str]) -> None:
    client = _mock_client()
    with patch("mismapi.cli.manage_openfga_roles.OpenFGAClient", return_value=client):
        exit_code = main(["revoke", "--role", "executor", "--user", "bob"])

    assert exit_code == 0
    client.delete_tuple.assert_awaited_once_with(
        user="user:bob", relation="executor", object_=PLATFORM_OBJECT
    )
    client.write_tuple.assert_not_awaited()
    client.close.assert_awaited_once()
    assert "Revoked 'executor' from user:bob" in capsys.readouterr().out


def test_main_closes_client_even_on_failure() -> None:
    client = _mock_client()
    client.write_tuple.side_effect = APIError(
        status_code=502, code="openfga_write_failed", detail="boom"
    )
    with patch("mismapi.cli.manage_openfga_roles.OpenFGAClient", return_value=client):
        exit_code = main(["grant", "--role", "uploader", "--user", "alice"])

    assert exit_code == 1
    client.close.assert_awaited_once()


def test_main_reports_api_error_on_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    client = _mock_client()
    client.write_tuple.side_effect = APIError(
        status_code=502, code="openfga_write_failed", detail="store unreachable"
    )
    with patch("mismapi.cli.manage_openfga_roles.OpenFGAClient", return_value=client):
        exit_code = main(["grant", "--role", "uploader", "--user", "alice"])

    assert exit_code == 1
    err = capsys.readouterr().err
    assert "store unreachable" in err
    assert "openfga_write_failed" in err

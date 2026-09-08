"""Unit tests for AuthorizationService (MISM-291).

Covers all methods in isolation by mocking ``OpenFGAClient.check`` /
``write_tuple``. No registry, no session, no FastAPI app — pure service-layer
logic only.

Test coverage targets:
  * Each assert method: allowed, denied, client=None (permissive), local issuer.
  * assert_can_view_model: anonymous path, FGA path, string-equality fallback.
  * _assert_run_relation: FGA path, triggered_by fallback, empty triggered_by.
  * get_platform_capabilities: no client (all False), local issuer (all True),
    per-role grants, mixed subset.
  * grant_model_tuples: both tuples written, skipped when no client.
  * grant_run_owner: owner tuple written, skipped when no client.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from mism_registry.enums import (
    ExecutionType,
    ResourceRegistrationStatus,
    ResourceType,
    ResourceVersionStatus,
    RunStatus,
)
from mism_registry.resource import Resource
from mism_registry.run import Run

from mismapi.auth.principal import AuthenticatedPrincipal
from mismapi.clients.openfga_client import OpenFGAClient
from mismapi.core.errors import APIError
from mismapi.services.authorization_service import AuthorizationService

_ROLES = ("uploader", "upload_reviewer", "image_checker", "executor")


# ── Helpers ───────────────────────────────────────────────────────────


def _principal(subject: str = "alice", *, issuer: str = "test") -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(subject=subject, issuer=issuer, audience="mism-api", scopes=set())


def _local_principal(subject: str = "anonymous") -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(subject=subject, issuer="local", audience="local", scopes=set())


def _client(allowed: bool) -> MagicMock:
    """A mock client whose ``check`` always returns ``allowed``."""
    client = MagicMock(spec=OpenFGAClient)
    client.check = AsyncMock(return_value=allowed)
    client.write_tuple = AsyncMock()
    return client


def _client_granting(*granted_relations: str) -> MagicMock:
    """A mock client whose ``check`` allows only the named relations."""
    client = MagicMock(spec=OpenFGAClient)

    async def _check(*, user: str, relation: str, object_: str) -> bool:
        return relation in granted_relations

    client.check = AsyncMock(side_effect=_check)
    client.write_tuple = AsyncMock()
    return client


def _authz(client: OpenFGAClient | None) -> AuthorizationService:
    return AuthorizationService(client=client)


def _resource(
    *,
    resource_id: str = "m-1",
    owner: str = "alice",
    registration_status: ResourceRegistrationStatus = ResourceRegistrationStatus.APPROVED,
) -> Resource:
    return Resource(
        id=resource_id,
        name="Example Model",
        resource_type=ResourceType.MODEL,
        location_uri=f"irods:///models/{resource_id}",
        execution_type=ExecutionType.PYTHON,
        execution_ref="",
        description="",
        version="0.1.0",
        version_status=ResourceVersionStatus.ACTIVE,
        registration_status=registration_status,
        owner=owner,
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
    )


def _run(*, run_id: str = "run-1", triggered_by: str = "alice") -> Run:
    return Run(
        id=run_id,
        model_id="m-1",
        model_version="0.1.0",
        status=RunStatus.COMPLETED,
        input_resource_ids=[],
        output_resource_ids=[],
        parameters={},
        triggered_by=triggered_by,
        notes="",
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
    )


# ── _client_for ───────────────────────────────────────────────────────


def test_client_for_returns_none_when_no_client_configured() -> None:
    authz = _authz(None)
    assert authz._client_for(_principal()) is None


def test_client_for_returns_none_for_local_issuer() -> None:
    mock = _client(True)
    authz = _authz(mock)
    assert authz._client_for(_local_principal()) is None


def test_client_for_returns_client_for_normal_principal() -> None:
    mock = _client(True)
    authz = _authz(mock)
    assert authz._client_for(_principal()) is mock


def test_client_for_returns_client_when_principal_is_none() -> None:
    """None principal is allowed (anonymous callers); client is still returned."""
    mock = _client(True)
    authz = _authz(mock)
    assert authz._client_for(None) is mock


# ── assert_uploader ───────────────────────────────────────────────────


async def test_assert_uploader_passes_when_allowed() -> None:
    mock = _client(True)
    await _authz(mock).assert_uploader(_principal("dana"))
    mock.check.assert_awaited_once_with(
        user="user:dana", relation="uploader", object_="platform:main"
    )


async def test_assert_uploader_raises_403_when_denied() -> None:
    with pytest.raises(APIError) as exc:
        await _authz(_client(False)).assert_uploader(_principal())
    assert exc.value.status_code == 403
    assert exc.value.code == "not_authorized"


async def test_assert_uploader_passes_without_client() -> None:
    await _authz(None).assert_uploader(_principal())  # no error


async def test_assert_uploader_passes_for_local_issuer() -> None:
    mock = _client(False)  # would deny if consulted
    await _authz(mock).assert_uploader(_local_principal())
    mock.check.assert_not_awaited()


# ── assert_upload_reviewer ────────────────────────────────────────────


async def test_assert_upload_reviewer_passes_when_allowed() -> None:
    mock = _client(True)
    await _authz(mock).assert_upload_reviewer(_principal("fiona"))
    mock.check.assert_awaited_once_with(
        user="user:fiona", relation="upload_reviewer", object_="platform:main"
    )


async def test_assert_upload_reviewer_raises_403_when_denied() -> None:
    with pytest.raises(APIError) as exc:
        await _authz(_client(False)).assert_upload_reviewer(_principal())
    assert exc.value.status_code == 403
    assert exc.value.code == "not_authorized"


async def test_assert_upload_reviewer_passes_without_client() -> None:
    await _authz(None).assert_upload_reviewer(_principal())


async def test_assert_upload_reviewer_passes_for_local_issuer() -> None:
    mock = _client(False)
    await _authz(mock).assert_upload_reviewer(_local_principal())
    mock.check.assert_not_awaited()


# ── assert_image_checker ──────────────────────────────────────────────


async def test_assert_image_checker_passes_when_allowed() -> None:
    mock = _client(True)
    await _authz(mock).assert_image_checker(_principal("gina"))
    mock.check.assert_awaited_once_with(
        user="user:gina", relation="image_checker", object_="platform:main"
    )


async def test_assert_image_checker_raises_403_when_denied() -> None:
    with pytest.raises(APIError) as exc:
        await _authz(_client(False)).assert_image_checker(_principal())
    assert exc.value.status_code == 403
    assert exc.value.code == "not_authorized"


async def test_assert_image_checker_passes_without_client() -> None:
    await _authz(None).assert_image_checker(_principal())


async def test_assert_image_checker_passes_for_local_issuer() -> None:
    mock = _client(False)
    await _authz(mock).assert_image_checker(_local_principal())
    mock.check.assert_not_awaited()


# ── assert_can_execute ────────────────────────────────────────────────


async def test_assert_can_execute_passes_when_allowed() -> None:
    mock = _client(True)
    await _authz(mock).assert_can_execute(_principal("henry"), model_id="m-1")
    mock.check.assert_awaited_once_with(
        user="user:henry", relation="can_execute", object_="model:m-1"
    )


async def test_assert_can_execute_raises_403_when_denied() -> None:
    with pytest.raises(APIError) as exc:
        await _authz(_client(False)).assert_can_execute(_principal(), model_id="m-1")
    assert exc.value.status_code == 403
    assert exc.value.code == "not_authorized"


async def test_assert_can_execute_uses_per_model_object() -> None:
    mock = _client(True)
    await _authz(mock).assert_can_execute(_principal(), model_id="some-other-model")
    mock.check.assert_awaited_once_with(
        user="user:alice", relation="can_execute", object_="model:some-other-model"
    )


async def test_assert_can_execute_passes_without_client() -> None:
    await _authz(None).assert_can_execute(_principal(), model_id="m-1")


async def test_assert_can_execute_passes_for_local_issuer() -> None:
    mock = _client(False)
    await _authz(mock).assert_can_execute(_local_principal(), model_id="m-1")
    mock.check.assert_not_awaited()


# ── assert_model_owner ────────────────────────────────────────────────


async def test_assert_model_owner_passes_when_allowed() -> None:
    mock = _client(True)
    await _authz(mock).assert_model_owner(_principal("iris"), model_id="m-1")
    mock.check.assert_awaited_once_with(user="user:iris", relation="owner", object_="model:m-1")


async def test_assert_model_owner_raises_403_when_denied() -> None:
    with pytest.raises(APIError) as exc:
        await _authz(_client(False)).assert_model_owner(_principal(), model_id="m-1")
    assert exc.value.status_code == 403
    assert exc.value.code == "not_authorized"


async def test_assert_model_owner_uses_per_model_object() -> None:
    mock = _client(True)
    await _authz(mock).assert_model_owner(_principal(), model_id="other-id")
    mock.check.assert_awaited_once_with(
        user="user:alice", relation="owner", object_="model:other-id"
    )


async def test_assert_model_owner_passes_without_client() -> None:
    await _authz(None).assert_model_owner(_principal(), model_id="m-1")


async def test_assert_model_owner_passes_for_local_issuer() -> None:
    mock = _client(False)
    await _authz(mock).assert_model_owner(_local_principal(), model_id="m-1")
    mock.check.assert_not_awaited()


# ── assert_can_view_model ─────────────────────────────────────────────


async def test_assert_can_view_model_passes_for_approved_anonymous() -> None:
    resource = _resource(registration_status=ResourceRegistrationStatus.APPROVED)
    await _authz(None).assert_can_view_model(None, resource=resource)  # no error


async def test_assert_can_view_model_raises_404_for_unapproved_anonymous() -> None:
    resource = _resource(registration_status=ResourceRegistrationStatus.PENDING_REVIEW)
    with pytest.raises(APIError) as exc:
        await _authz(None).assert_can_view_model(None, resource=resource)
    assert exc.value.status_code == 404


async def test_assert_can_view_model_passes_with_fga_allowed() -> None:
    mock = _client(True)
    resource = _resource(resource_id="m-2")
    await _authz(mock).assert_can_view_model(_principal("jack"), resource=resource)
    mock.check.assert_awaited_once_with(user="user:jack", relation="can_view", object_="model:m-2")


async def test_assert_can_view_model_raises_404_with_fga_denied() -> None:
    with pytest.raises(APIError) as exc:
        await _authz(_client(False)).assert_can_view_model(_principal(), resource=_resource())
    assert exc.value.status_code == 404
    assert exc.value.code == "not_found"


async def test_assert_can_view_model_fallback_passes_for_owner() -> None:
    """No FGA client: owner can view their own draft."""
    resource = _resource(
        owner="kara", registration_status=ResourceRegistrationStatus.PENDING_REVIEW
    )
    await _authz(None).assert_can_view_model(_principal("kara"), resource=resource)


async def test_assert_can_view_model_fallback_raises_404_for_non_owner_draft() -> None:
    """No FGA client: non-owner cannot see a draft."""
    resource = _resource(
        owner="kara", registration_status=ResourceRegistrationStatus.PENDING_REVIEW
    )
    with pytest.raises(APIError) as exc:
        await _authz(None).assert_can_view_model(_principal("liam"), resource=resource)
    assert exc.value.status_code == 404


async def test_assert_can_view_model_fallback_passes_for_approved_non_owner() -> None:
    """No FGA client: approved models are public."""
    resource = _resource(owner="kara", registration_status=ResourceRegistrationStatus.APPROVED)
    await _authz(None).assert_can_view_model(_principal("liam"), resource=resource)


async def test_assert_can_view_model_local_issuer_uses_fallback_not_fga() -> None:
    """local issuer → _client_for returns None → string-equality fallback."""
    mock = _client(False)  # would deny if consulted
    resource = _resource(
        owner="anonymous", registration_status=ResourceRegistrationStatus.PENDING_REVIEW
    )
    # Owner matches local principal — should pass without consulting FGA.
    await _authz(mock).assert_can_view_model(_local_principal("anonymous"), resource=resource)
    mock.check.assert_not_awaited()


# ── assert_can_view_run / assert_can_cancel_run ───────────────────────


async def test_assert_can_view_run_passes_with_fga_allowed() -> None:
    mock = _client(True)
    run = _run(run_id="r-1")
    await _authz(mock).assert_can_view_run(_principal("mona"), run=run)
    mock.check.assert_awaited_once_with(user="user:mona", relation="can_view", object_="run:r-1")


async def test_assert_can_view_run_raises_404_with_fga_denied() -> None:
    with pytest.raises(APIError) as exc:
        await _authz(_client(False)).assert_can_view_run(_principal(), run=_run())
    assert exc.value.status_code == 404
    assert exc.value.code == "not_found"


async def test_assert_can_cancel_run_passes_with_fga_allowed() -> None:
    mock = _client(True)
    run = _run(run_id="r-2")
    await _authz(mock).assert_can_cancel_run(_principal("nina"), run=run)
    mock.check.assert_awaited_once_with(user="user:nina", relation="can_cancel", object_="run:r-2")


async def test_assert_can_cancel_run_raises_404_with_fga_denied() -> None:
    with pytest.raises(APIError) as exc:
        await _authz(_client(False)).assert_can_cancel_run(_principal(), run=_run())
    assert exc.value.status_code == 404


async def test_run_relation_fallback_passes_for_triggering_principal() -> None:
    """No FGA client: triggered_by match allows access."""
    run = _run(triggered_by="oscar")
    await _authz(None).assert_can_view_run(_principal("oscar"), run=run)


async def test_run_relation_fallback_raises_404_for_non_owner() -> None:
    run = _run(triggered_by="oscar")
    with pytest.raises(APIError) as exc:
        await _authz(None).assert_can_view_run(_principal("pete"), run=run)
    assert exc.value.status_code == 404


async def test_run_relation_fallback_raises_404_for_empty_triggered_by() -> None:
    """Empty triggered_by is owned by nobody — historical rows stay invisible."""
    run = _run(triggered_by="")
    with pytest.raises(APIError) as exc:
        await _authz(None).assert_can_view_run(_principal("alice"), run=run)
    assert exc.value.status_code == 404


async def test_run_relation_local_issuer_uses_fallback() -> None:
    mock = _client(False)
    run = _run(triggered_by="anonymous")
    await _authz(mock).assert_can_view_run(_local_principal("anonymous"), run=run)
    mock.check.assert_not_awaited()


# ── get_platform_capabilities ─────────────────────────────────────────


async def test_capabilities_all_false_without_client() -> None:
    result = await _authz(None).get_platform_capabilities(_principal())
    assert result == dict.fromkeys(_ROLES, False)


async def test_capabilities_all_true_for_local_issuer() -> None:
    mock = _client_granting()  # would deny everything if consulted
    result = await _authz(mock).get_platform_capabilities(_local_principal())
    assert result == dict.fromkeys(_ROLES, True)
    mock.check.assert_not_awaited()


async def test_capabilities_all_true_when_all_roles_granted() -> None:
    mock = _client_granting(*_ROLES)
    result = await _authz(mock).get_platform_capabilities(_principal("quinn"))
    assert result == dict.fromkeys(_ROLES, True)
    assert mock.check.await_count == len(_ROLES)
    for role in _ROLES:
        mock.check.assert_any_await(user="user:quinn", relation=role, object_="platform:main")


async def test_capabilities_all_false_when_no_roles_granted() -> None:
    result = await _authz(_client_granting()).get_platform_capabilities(_principal())
    assert result == dict.fromkeys(_ROLES, False)


async def test_capabilities_reflects_uploader_only() -> None:
    result = await _authz(_client_granting("uploader")).get_platform_capabilities(_principal())
    assert result == {
        "uploader": True,
        "upload_reviewer": False,
        "image_checker": False,
        "executor": False,
    }


async def test_capabilities_reflects_mixed_subset() -> None:
    mock = _client_granting("upload_reviewer", "executor")
    result = await _authz(mock).get_platform_capabilities(_principal())
    assert result == {
        "uploader": False,
        "upload_reviewer": True,
        "image_checker": False,
        "executor": True,
    }


# ── grant_model_tuples ────────────────────────────────────────────────


async def test_grant_model_tuples_writes_owner_and_platform() -> None:
    mock = _client(True)
    await _authz(mock).grant_model_tuples(_principal("rosa"), model_id="m-99")
    assert mock.write_tuple.await_count == 2
    mock.write_tuple.assert_any_await(user="user:rosa", relation="owner", object_="model:m-99")
    mock.write_tuple.assert_any_await(
        user="platform:main", relation="platform", object_="model:m-99"
    )


async def test_grant_model_tuples_skipped_without_client() -> None:
    mock = _client(True)
    await _authz(None).grant_model_tuples(_principal(), model_id="m-99")
    mock.write_tuple.assert_not_awaited()


async def test_grant_model_tuples_skipped_for_local_issuer() -> None:
    mock = _client(True)
    await _authz(mock).grant_model_tuples(_local_principal(), model_id="m-99")
    mock.write_tuple.assert_not_awaited()


# ── grant_model_viewer_wildcard ───────────────────────────────────────


async def test_grant_model_viewer_wildcard_writes_user_star_tuple() -> None:
    mock = _client(True)
    await _authz(mock).grant_model_viewer_wildcard(_principal("reviewer"), model_id="m-7")
    mock.write_tuple.assert_awaited_once_with(user="user:*", relation="viewer", object_="model:m-7")


async def test_grant_model_viewer_wildcard_skipped_without_client() -> None:
    mock = _client(True)
    await _authz(None).grant_model_viewer_wildcard(_principal(), model_id="m-7")
    mock.write_tuple.assert_not_awaited()


async def test_grant_model_viewer_wildcard_skipped_for_local_issuer() -> None:
    mock = _client(True)
    await _authz(mock).grant_model_viewer_wildcard(_local_principal(), model_id="m-7")
    mock.write_tuple.assert_not_awaited()


# ── grant_run_owner ───────────────────────────────────────────────────


async def test_grant_run_owner_writes_owner_tuple() -> None:
    mock = _client(True)
    await _authz(mock).grant_run_owner(_principal("sam"), run_id="r-42")
    mock.write_tuple.assert_awaited_once_with(user="user:sam", relation="owner", object_="run:r-42")


async def test_grant_run_owner_skipped_without_client() -> None:
    mock = _client(True)
    await _authz(None).grant_run_owner(_principal(), run_id="r-42")
    mock.write_tuple.assert_not_awaited()


async def test_grant_run_owner_skipped_for_local_issuer() -> None:
    mock = _client(True)
    await _authz(mock).grant_run_owner(_local_principal(), run_id="r-42")
    mock.write_tuple.assert_not_awaited()

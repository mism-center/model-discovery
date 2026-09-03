"""Unit tests for RegistryService's platform-role capabilities summary (MISM-291).

Covers `get_platform_capabilities`, which powers `GET /auth/capabilities`:
reports whether the calling principal holds each of the four platform-wide
roles (`uploader`, `upload_reviewer`, `image_checker`, `executor`) as booleans,
without raising. Mirrors the existing `_assert_*` gate tests' style
(`test_registry_service_reviewer_gate.py` et al.) for the "no client" and
"local issuer" skip-rule cases, but those two cases report *different*
booleans here (all False vs. all True) — see the method's own docstring for
why that's a deliberate asymmetry with `_assert_*`'s shared skip rule.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from mism_registry.in_memory import InMemoryRegistry

from mismapi.auth.principal import AuthenticatedPrincipal
from mismapi.clients.openfga_client import OpenFGAClient
from mismapi.services.registry_service import RegistryService

_ROLES = ("uploader", "upload_reviewer", "image_checker", "executor")


def _principal(subject: str = "fiona") -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        subject=subject,
        issuer="test",
        audience="mism-api",
        scopes=set(),
    )


def _make_service(openfga_client: OpenFGAClient | None) -> RegistryService:
    registry = InMemoryRegistry()
    session = MagicMock()
    return RegistryService(registry=registry, session=session, openfga_client=openfga_client)


def _client_granting(*granted_roles: str) -> MagicMock:
    """A mocked OpenFGAClient whose `check` allows only `granted_roles`."""
    client = MagicMock(spec=OpenFGAClient)

    async def _check(*, user: str, relation: str, object_: str) -> bool:
        return relation in granted_roles

    client.check = AsyncMock(side_effect=_check)
    return client


# ── No OpenFGA client configured — all four False ───────────────────


async def test_capabilities_all_false_without_openfga_client() -> None:
    service = _make_service(None)

    result = await service.get_platform_capabilities(_principal())

    assert result == dict.fromkeys(_ROLES, False)


# ── issuer == "local" — all four True, client never consulted ───────


async def test_capabilities_all_true_for_local_issuer() -> None:
    client = _client_granting()  # would deny everything if consulted
    service = _make_service(client)
    local_principal = AuthenticatedPrincipal(
        subject="anonymous", issuer="local", audience="local", scopes=set()
    )

    result = await service.get_platform_capabilities(local_principal)

    assert result == dict.fromkeys(_ROLES, True)
    client.check.assert_not_awaited()


# ── Real OpenFGA client — per-role grants ────────────────────────────


async def test_capabilities_all_true_when_all_roles_granted() -> None:
    client = _client_granting(*_ROLES)
    service = _make_service(client)

    result = await service.get_platform_capabilities(_principal("gina"))

    assert result == dict.fromkeys(_ROLES, True)
    assert client.check.await_count == len(_ROLES)
    for role in _ROLES:
        client.check.assert_any_await(user="user:gina", relation=role, object_="platform:main")


async def test_capabilities_all_false_when_no_roles_granted() -> None:
    client = _client_granting()
    service = _make_service(client)

    result = await service.get_platform_capabilities(_principal("henry"))

    assert result == dict.fromkeys(_ROLES, False)


async def test_capabilities_reflects_uploader_only() -> None:
    client = _client_granting("uploader")
    service = _make_service(client)

    result = await service.get_platform_capabilities(_principal("iris"))

    assert result == {
        "uploader": True,
        "upload_reviewer": False,
        "image_checker": False,
        "executor": False,
    }


async def test_capabilities_reflects_upload_reviewer_only() -> None:
    client = _client_granting("upload_reviewer")
    service = _make_service(client)

    result = await service.get_platform_capabilities(_principal("jack"))

    assert result == {
        "uploader": False,
        "upload_reviewer": True,
        "image_checker": False,
        "executor": False,
    }


async def test_capabilities_reflects_image_checker_only() -> None:
    client = _client_granting("image_checker")
    service = _make_service(client)

    result = await service.get_platform_capabilities(_principal("kara"))

    assert result == {
        "uploader": False,
        "upload_reviewer": False,
        "image_checker": True,
        "executor": False,
    }


async def test_capabilities_reflects_executor_only() -> None:
    client = _client_granting("executor")
    service = _make_service(client)

    result = await service.get_platform_capabilities(_principal("liam"))

    assert result == {
        "uploader": False,
        "upload_reviewer": False,
        "image_checker": False,
        "executor": True,
    }


async def test_capabilities_reflects_a_mixed_subset() -> None:
    client = _client_granting("upload_reviewer", "executor")
    service = _make_service(client)

    result = await service.get_platform_capabilities(_principal("mona"))

    assert result == {
        "uploader": False,
        "upload_reviewer": True,
        "image_checker": False,
        "executor": True,
    }

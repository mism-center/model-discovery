"""Unit tests for RegistryService.search() gate logic.

Covers:
- version_status=active is always forced
- registration_status=approved is forced for anonymous and local-dev callers
- Authenticated callers can override registration_status gate and get an
  automatic owner constraint when no owner filter is present
- image_review_status filtering adds the same owner constraint
- Callers who already supply an owner filter are not double-constrained
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from mism_registry.search import FieldFilter, SearchQuery

from mismapi.auth.principal import AuthenticatedPrincipal
from mismapi.core.errors import APIError
from mismapi.services.registry_service import RegistryService


def _principal(subject: str = "alice", issuer: str = "test") -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(subject=subject, issuer=issuer, audience="mism-api", scopes=set())


def _local_principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        subject="anonymous", issuer="local", audience="mism-api", scopes=set()
    )


def _make_service() -> tuple[RegistryService, MagicMock]:
    # Swap out the real postgres search with a spy that captures the query.
    # We don't test the actual search results — only the filters that reach it.
    from mism_registry.backends.postgres import PostgresRegistry

    fake_registry = MagicMock(spec=PostgresRegistry)
    fake_registry.search_resources.return_value = MagicMock(
        total=0, resources=[], scores=None, aggs={}
    )
    service = RegistryService(registry=fake_registry, session=MagicMock())
    return service, fake_registry


def _filters_sent(fake_registry: MagicMock) -> tuple[FieldFilter, ...]:
    """Extract the filters from the SearchQuery passed to search_resources."""
    call_args = fake_registry.search_resources.call_args
    query: SearchQuery = call_args[0][0]
    return query.filters


# ── version_status gate ───────────────────────────────────────────────────────


def test_version_status_always_forced_for_anonymous() -> None:
    service, fake = _make_service()
    service.search(SearchQuery(), principal=None)
    fields = {f.field: f.value for f in _filters_sent(fake)}
    assert fields["version_status"] == "active"


def test_version_status_always_forced_for_authenticated() -> None:
    service, fake = _make_service()
    service.search(SearchQuery(), principal=_principal())
    fields = {f.field: f.value for f in _filters_sent(fake)}
    assert fields["version_status"] == "active"


def test_version_status_cannot_be_overridden_by_anonymous() -> None:
    service, fake = _make_service()
    q = SearchQuery(filters=(FieldFilter("version_status", "eq", "archived"),))
    service.search(q, principal=None)
    fields = {f.field: f.value for f in _filters_sent(fake)}
    # Gate replaces the caller's value.
    assert fields["version_status"] == "active"


def test_version_status_cannot_be_overridden_by_authenticated() -> None:
    service, fake = _make_service()
    q = SearchQuery(filters=(FieldFilter("version_status", "eq", "archived"),))
    service.search(q, principal=_principal())
    fields = {f.field: f.value for f in _filters_sent(fake)}
    assert fields["version_status"] == "active"


# ── registration_status gate — anonymous / local-dev ─────────────────────────


def test_registration_status_forced_for_anonymous() -> None:
    service, fake = _make_service()
    service.search(SearchQuery(), principal=None)
    fields = {f.field: f.value for f in _filters_sent(fake)}
    assert fields["registration_status"] == "approved"


def test_registration_status_forced_for_local_issuer() -> None:
    service, fake = _make_service()
    service.search(SearchQuery(), principal=_local_principal())
    fields = {f.field: f.value for f in _filters_sent(fake)}
    assert fields["registration_status"] == "approved"


def test_registration_status_gate_overrides_anonymous_attempt() -> None:
    service, fake = _make_service()
    q = SearchQuery(filters=(FieldFilter("registration_status", "in", ["pending_review"]),))
    service.search(q, principal=None)
    fields = {f.field: f.value for f in _filters_sent(fake)}
    # Anonymous caller's filter is dropped; gate takes precedence.
    assert fields["registration_status"] == "approved"


# ── registration_status gate — authenticated override ────────────────────────


def test_authenticated_can_override_registration_status_gate() -> None:
    service, fake = _make_service()
    q = SearchQuery(filters=(FieldFilter("registration_status", "in", ["pending_review"]),))
    service.search(q, principal=_principal("alice"))
    # Gate NOT added; caller's filter remains.
    assert "registration_status" not in {
        f.field: f.value for f in _filters_sent(fake) if f.value == "approved"
    }
    # Owner constraint IS added automatically.
    owner_filters = [f for f in _filters_sent(fake) if f.field == "owner"]
    assert len(owner_filters) == 1
    assert owner_filters[0].value == "alice"


def test_owner_constraint_not_added_when_owner_already_present() -> None:
    """Caller who supplies their own owner filter is not double-constrained."""
    service, fake = _make_service()
    q = SearchQuery(
        filters=(
            FieldFilter("registration_status", "in", ["pending_review"]),
            FieldFilter("owner", "eq", "alice"),
        )
    )
    service.search(q, principal=_principal("alice"))
    owner_filters = [f for f in _filters_sent(fake) if f.field == "owner"]
    assert len(owner_filters) == 1  # not doubled


def test_owner_constraint_uses_principal_subject() -> None:
    service, fake = _make_service()
    q = SearchQuery(filters=(FieldFilter("registration_status", "in", ["pending_review"]),))
    service.search(q, principal=_principal("bob"))
    owner_filters = [f for f in _filters_sent(fake) if f.field == "owner"]
    assert owner_filters[0].value == "bob"


# ── image_review_status filtering ────────────────────────────────────────────


def test_image_review_status_filter_adds_owner_constraint() -> None:
    """image_review_status filter always adds owner scope for real users."""
    service, fake = _make_service()
    q = SearchQuery(filters=(FieldFilter("image_review_status", "in", ["pending_image_check"]),))
    service.search(q, principal=_principal("carol"))
    # registration_status gate is still active (caller didn't set it).
    fields = {f.field: f.value for f in _filters_sent(fake)}
    assert fields["registration_status"] == "approved"
    # Owner constraint added.
    owner_filters = [f for f in _filters_sent(fake) if f.field == "owner"]
    assert len(owner_filters) == 1
    assert owner_filters[0].value == "carol"


def test_image_review_status_no_owner_added_for_local_issuer() -> None:
    service, fake = _make_service()
    q = SearchQuery(filters=(FieldFilter("image_review_status", "in", ["pending_image_check"]),))
    service.search(q, principal=_local_principal())
    owner_filters = [f for f in _filters_sent(fake) if f.field == "owner"]
    assert owner_filters == []


# ── validation still fires ────────────────────────────────────────────────────


def test_unknown_filter_field_raises_400() -> None:
    service, _ = _make_service()
    q = SearchQuery(filters=(FieldFilter("nonexistent_field", "eq", "x"),))
    with pytest.raises(APIError) as exc:
        service.search(q, principal=None)
    assert exc.value.status_code == 400
    assert exc.value.code == "invalid_filter"


def test_unknown_agg_field_raises_400() -> None:
    service, _ = _make_service()
    q = SearchQuery(agg_fields=("nonexistent_field",))
    with pytest.raises(APIError) as exc:
        service.search(q, principal=None)
    assert exc.value.status_code == 400
    assert exc.value.code == "invalid_aggregation"

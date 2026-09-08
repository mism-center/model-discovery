"""Centralized OpenFGA authorization service.

All relation checks, tuple writes, and capability queries go through this
class. Other services (e.g. RegistryService) inject it instead of calling
OpenFGAClient directly.

See Docs/OpenFGA/AuthorizationService-Refactor.md for the full design.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from mism_registry.enums import ResourceRegistrationStatus
from mism_registry.resource import Resource
from mism_registry.run import Run

from mismapi.auth.principal import AuthenticatedPrincipal
from mismapi.clients.openfga_client import OpenFGAClient
from mismapi.core.errors import APIError

log = logging.getLogger(__name__)

_PLATFORM_OBJECT = "platform:main"
_PLATFORM_ROLES: tuple[str, ...] = ("uploader", "upload_reviewer", "image_checker", "executor")

Relation = Literal[
    "owner",
    "can_view",
    "can_execute",
    "can_cancel",
    "uploader",
    "upload_reviewer",
    "image_checker",
    "executor",
]


@dataclass(frozen=True)
class PlatformCapabilities:
    """Platform-wide role grants for an authenticated principal."""

    uploader: bool
    upload_reviewer: bool
    image_checker: bool
    executor: bool


class AuthorizationService:
    """Single entry point for all OpenFGA permission checks and tuple writes."""

    def __init__(self, client: OpenFGAClient | None) -> None:
        # None means OpenFGA is disabled (local dev); callers receive permissive defaults.
        self._client = client

    # ── Internal helpers ─────────────────────────────────────────────

    def _client_for(self, principal: AuthenticatedPrincipal | None) -> OpenFGAClient | None:
        """Return the configured OpenFGA client, or None if calls should be skipped.

        None when no client is configured (local dev without a running OpenFGA
        instance) or when ``issuer == "local"`` (set by ``auth/base.py`` when
        ``settings.disable_auth`` is True). Both conditions skip tuple writes
        as well as checks — a write would fail with a real network error and
        reject the request anyway.
        """
        if self._client is None:
            return None
        if principal is not None and principal.issuer == "local":
            return None
        return self._client

    # ── Platform-role gates (object = platform:main) ─────────────────

    async def assert_uploader(self, principal: AuthenticatedPrincipal) -> None:
        """Gate resource creation on the platform-wide ``uploader`` role."""
        client = self._client_for(principal)
        if client is None:
            return
        allowed = await client.check(
            user=f"user:{principal.subject}",
            relation="uploader",
            object_=_PLATFORM_OBJECT,
        )
        if not allowed:
            raise APIError(
                status_code=403,
                code="not_authorized",
                detail="Principal does not hold the platform uploader role.",
            )

    async def assert_upload_reviewer(self, principal: AuthenticatedPrincipal) -> None:
        """Gate metadata-review actions on the platform-wide ``upload_reviewer`` role.

        Global, not per-submission: any holder of this role may review any
        ``PENDING_REVIEW`` model, including one they uploaded themselves.
        """
        client = self._client_for(principal)
        if client is None:
            return
        allowed = await client.check(
            user=f"user:{principal.subject}",
            relation="upload_reviewer",
            object_=_PLATFORM_OBJECT,
        )
        if not allowed:
            raise APIError(
                status_code=403,
                code="not_authorized",
                detail="Principal does not hold the platform upload_reviewer role.",
            )

    async def assert_image_checker(self, principal: AuthenticatedPrincipal) -> None:
        """Gate image-review actions on the platform-wide ``image_checker`` role.

        Global, not per-submission: any holder of this role may vet any model's
        image, including one they themselves uploaded.
        """
        client = self._client_for(principal)
        if client is None:
            return
        allowed = await client.check(
            user=f"user:{principal.subject}",
            relation="image_checker",
            object_=_PLATFORM_OBJECT,
        )
        if not allowed:
            raise APIError(
                status_code=403,
                code="not_authorized",
                detail="Principal does not hold the platform image_checker role.",
            )

    # ── Per-model checks ─────────────────────────────────────────────

    async def assert_can_execute(self, principal: AuthenticatedPrincipal, *, model_id: str) -> None:
        """Gate execution on the per-model ``can_execute`` relation.

        Checks ``model:{model_id}`` (not ``platform:main``): the relation is a
        union of ``owner`` OR ``platform#executor`` via ``tupleToUserset``.
        """
        client = self._client_for(principal)
        if client is None:
            return
        allowed = await client.check(
            user=f"user:{principal.subject}",
            relation="can_execute",
            object_=f"model:{model_id}",
        )
        if not allowed:
            raise APIError(
                status_code=403,
                code="not_authorized",
                detail="Principal is not authorized to execute this model.",
            )

    async def assert_model_owner(self, principal: AuthenticatedPrincipal, *, model_id: str) -> None:
        """Gate mutation operations on per-model ownership.

        Checks the ``owner`` relation on ``model:{model_id}`` — raises 403 (not
        404) matching the mutation-gate convention.

        When no FGA client is configured (local dev), the check is skipped.
        Callers that need a Postgres ownership fallback should additionally call
        ``RegistryService.get_resource_and_assert_ownership``.
        """
        client = self._client_for(principal)
        if client is None:
            return
        allowed = await client.check(
            user=f"user:{principal.subject}",
            relation="owner",
            object_=f"model:{model_id}",
        )
        if not allowed:
            raise APIError(
                status_code=403,
                code="not_authorized",
                detail=f"Principal is not the owner of model '{model_id}'.",
            )

    async def assert_can_view_model(
        self,
        principal: AuthenticatedPrincipal | None,
        *,
        resource: Resource,
    ) -> None:
        """Raise APIError(404) if ``principal`` cannot view ``resource``.

        Raises 404 (not 403) on the id-oracle-avoidance convention: a caller
        who cannot see a resource must not be told it exists.

        Three resolution paths:
        * Anonymous (``principal is None``): approved == public; no identity to
          check ownership against.
        * Authenticated + FGA client: ``can_view`` on ``model:{id}``.
        * Authenticated, no FGA client (``issuer == "local"`` or unconfigured):
          string-equality fallback — approved OR owner match.
        """
        _not_visible = APIError(
            status_code=404,
            code="not_found",
            detail=f"Model '{resource.id}' not found.",
        )
        if principal is None:
            if resource.registration_status != ResourceRegistrationStatus.APPROVED:
                raise _not_visible
            return

        client = self._client_for(principal)
        if client is not None:
            allowed = await client.check(
                user=f"user:{principal.subject}",
                relation="can_view",
                object_=f"model:{resource.id}",
            )
            if not allowed:
                raise _not_visible
            return

        # No FGA client (local dev or unconfigured): string-equality fallback.
        public = resource.registration_status == ResourceRegistrationStatus.APPROVED
        owned = bool(resource.owner) and resource.owner == principal.subject
        if not (public or owned):
            raise _not_visible

    # ── Per-run checks ───────────────────────────────────────────────

    async def _assert_run_relation(
        self,
        principal: AuthenticatedPrincipal,
        *,
        run: Run,
        relation: str,
    ) -> None:
        """Check ``relation`` on ``run:{id}``.

        Raises 404 (not 403) on the id-oracle-avoidance convention. Fallback
        when no FGA client: string equality on ``run.triggered_by``. Empty
        ``triggered_by`` is owned by nobody — historical rows stay invisible.
        """
        _not_visible = APIError(
            status_code=404,
            code="not_found",
            detail=f"Run '{run.id}' not found.",
        )
        client = self._client_for(principal)
        if client is not None:
            allowed = await client.check(
                user=f"user:{principal.subject}",
                relation=relation,
                object_=f"run:{run.id}",
            )
            if not allowed:
                raise _not_visible
            return

        # No FGA client: string-equality fallback.
        if not run.triggered_by or run.triggered_by != principal.subject:
            raise _not_visible

    async def assert_can_view_run(self, principal: AuthenticatedPrincipal, *, run: Run) -> None:
        """Gate GET /runs/{id}: principal must hold ``can_view`` on the run."""
        await self._assert_run_relation(principal, run=run, relation="can_view")

    async def assert_can_cancel_run(self, principal: AuthenticatedPrincipal, *, run: Run) -> None:
        """Gate DELETE /runs/{id}: principal must hold ``can_cancel`` on the run."""
        await self._assert_run_relation(principal, run=run, relation="can_cancel")

    # ── Capabilities ─────────────────────────────────────────────────

    async def get_platform_capabilities(self, principal: AuthenticatedPrincipal) -> dict[str, bool]:
        """Report which platform-wide OpenFGA roles ``principal`` holds.

        Powers ``GET /auth/capabilities``. Deliberately asymmetric between the
        two skip conditions: ``issuer == "local"`` returns all True (dev
        permissiveness), but an *unconfigured* client returns all False (a
        status endpoint that reports True for unchecked grants would be
        misleading rather than merely permissive).
        """
        if self._client is None:
            return dict.fromkeys(_PLATFORM_ROLES, False)
        if principal.issuer == "local":
            return dict.fromkeys(_PLATFORM_ROLES, True)
        client = self._client
        user = f"user:{principal.subject}"
        return {
            role: await client.check(user=user, relation=role, object_=_PLATFORM_OBJECT)
            for role in _PLATFORM_ROLES
        }

    # ── Tuple writes ─────────────────────────────────────────────────

    async def grant_model_tuples(self, principal: AuthenticatedPrincipal, *, model_id: str) -> None:
        """Write the ownership and platform boilerplate tuples for a new model.

        Writes two tuples:
        * ``user:{subject} → owner → model:{id}``
        * ``platform:main → platform → model:{id}``

        The platform tuple is required for ``model#can_execute``'s
        ``tupleToUserset`` (``owner`` OR ``platform#executor``) to resolve.
        Both writes are skipped per ``_client_for``'s rules.
        """
        client = self._client_for(principal)
        if client is None:
            return
        model_object = f"model:{model_id}"
        await client.write_tuple(
            user=f"user:{principal.subject}", relation="owner", object_=model_object
        )
        await client.write_tuple(user=_PLATFORM_OBJECT, relation="platform", object_=model_object)

    async def grant_model_viewer_wildcard(
        self, principal: AuthenticatedPrincipal, *, model_id: str
    ) -> None:
        """Write the public-visibility tuple for an approved model.

        Writes ``user:* → viewer → model:{id}`` so OpenFGA can answer
        ``can_view`` checks for any caller (including anonymous, via the
        ``user:*`` wildcard) once a model reaches APPROVED status.
        Skipped per ``_client_for``'s rules.
        """
        client = self._client_for(principal)
        if client is None:
            return
        await client.write_tuple(user="user:*", relation="viewer", object_=f"model:{model_id}")

    async def grant_run_owner(self, principal: AuthenticatedPrincipal, *, run_id: str) -> None:
        """Write the ownership tuple for a new run.

        Writes ``user:{subject} → owner → run:{id}`` so OpenFGA can answer
        ``can_view`` / ``can_cancel`` checks via the ``owner`` relation.
        Skipped per ``_client_for``'s rules.
        """
        client = self._client_for(principal)
        if client is None:
            return
        await client.write_tuple(
            user=f"user:{principal.subject}", relation="owner", object_=f"run:{run_id}"
        )

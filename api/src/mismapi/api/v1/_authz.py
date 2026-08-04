"""Authorization guards shared by the v1 routers.

Kept out of ``_run_helpers`` (pure response mappers) so response shaping stays
free of policy.

Both guards raise **404, not 403**, on a mismatch. A caller who does not own a
run — or may not yet see a model — must not be able to tell "exists but isn't
yours" apart from "doesn't exist", otherwise these endpoints become an id
oracle: enumerate ids, keep the 403s.

Model visibility deliberately reuses the gate the search path already applies
(``RegistryService._SEARCH_GATE`` = version_status active + registration_status
approved): anything not yet approved is visible only to its owner. Owner
comparison is against ``principal.subject`` because that is what
``RegistryService.create_model`` stores (``owner=owner or principal.subject``).
"""

from mism_registry.enums import ResourceRegistrationStatus
from mism_registry.resource import Resource
from mism_registry.run import Run

from mismapi.auth.principal import AuthenticatedPrincipal
from mismapi.core.errors import APIError

#: Registration states whose models any caller — including anonymous — may read.
PUBLIC_REGISTRATION_STATUSES = frozenset({ResourceRegistrationStatus.APPROVED})


def _not_found(kind: str, identifier: str) -> APIError:
    return APIError(
        status_code=404,
        code="not_found",
        detail=f"{kind} {identifier} not found.",
    )


def owns_run(run: Run, principal: AuthenticatedPrincipal | None) -> bool:
    """Whether ``principal`` triggered ``run``.

    Anonymous callers own nothing, and a run with an empty ``triggered_by`` is
    owned by nobody — historical rows predating attribution stay invisible
    rather than becoming public.
    """
    if principal is None:
        return False
    return bool(run.triggered_by) and run.triggered_by == principal.subject


def assert_run_owner(run: Run, principal: AuthenticatedPrincipal) -> None:
    """Reject callers who did not trigger ``run``."""
    if not owns_run(run, principal):
        raise _not_found("Run", run.id)


def assert_resource_owner(resource: Resource, principal: AuthenticatedPrincipal) -> None:
    """Reject callers who do not own ``resource``.

    For actions that consume the deployment's own resources — kicking off an
    annotation job spends the server-side LLM budget — being able to *see* a
    resource must not confer the right to spend against it. Ownership is the
    bar, not visibility, so this is deliberately stricter than
    :func:`assert_model_visible`.
    """
    if not resource.owner or resource.owner != principal.subject:
        raise _not_found("Resource", resource.id)


def model_visible_to(model: Resource, principal: AuthenticatedPrincipal | None) -> bool:
    """Whether ``principal`` may read ``model``."""
    if model.registration_status in PUBLIC_REGISTRATION_STATUSES:
        return True
    return principal is not None and bool(model.owner) and model.owner == principal.subject


def assert_model_visible(model: Resource, principal: AuthenticatedPrincipal | None) -> None:
    """Reject reads of models that are not yet public and not owned by the caller."""
    if not model_visible_to(model, principal):
        raise _not_found("Model", model.id)

"""Post-login `return_to` resolution via a route-key allowlist.

Client sends a route key (plus route's query string).
The server maps the key to a path it controls, so an
attacker can't steer a freshly authenticated user off-origin.
Unknown or missing keys fall back to the default landing path.

Keep `ROUTE_PATHS` / `PARAMETERIZED_ROUTE_PATHS` in sync with the UI route table
(`ui/app/routes.ts`). Drift is safe-by-default: an unmapped key resolves to
`DEFAULT_LANDING_PATH`.

Parameterized routes (e.g. `/models/{id}`) accept exactly one id, and the id is
validated as a UUID with `uuid.UUID` before substitution. That keeps the client
supplying *data*, never a path: a value carrying `/`, `..`, a scheme, or a host
fails UUID parsing and falls back to the default landing path. The server still
owns every character of the resulting path template.
"""

from __future__ import annotations

from urllib.parse import parse_qsl
from uuid import UUID

from mismapi.utils import merge_query_params

DEFAULT_LANDING_PATH = "/"

ROUTE_PATHS: dict[str, str] = {
    "search": "/search",
    "runs": "/runs",
    "upload": "/upload",
    # Carries the model under review as `?id=<uuid>`; the query rides along via
    # `return_to_query` rather than being part of the path, so this stays a
    # static key.
    "annotation-review": "/annotation-review",
}

#: Route keys whose path needs one caller-supplied id. Values are `str.format`
#: templates with a single `{id}` field.
PARAMETERIZED_ROUTE_PATHS: dict[str, str] = {
    "model": "/models/{id}",
}


def _safe_id(raw: str | None) -> str | None:
    """Return `raw` only if it is a well-formed UUID, else `None`.

    Model ids are UUIDs. Parsing with `uuid.UUID` (rather than pattern-matching
    or escaping) means anything that is not exactly a UUID — including path
    separators, traversal sequences and absolute URLs — is rejected outright.
    """
    if not raw:
        return None
    try:
        return str(UUID(raw))
    except (ValueError, AttributeError, TypeError):
        return None


def resolve_return_to(
    route_key: str | None,
    query: str | None,
    resource_id: str | None = None,
) -> str:
    """Resolve a client-supplied route key + query string to a safe local path."""
    path = ROUTE_PATHS.get(route_key or "")

    if path is None:
        template = PARAMETERIZED_ROUTE_PATHS.get(route_key or "")
        safe_id = _safe_id(resource_id)
        if template is None or safe_id is None:
            return DEFAULT_LANDING_PATH
        path = template.format(id=safe_id)

    if not query:
        return path
    return merge_query_params(path, dict(parse_qsl(query, keep_blank_values=True)))

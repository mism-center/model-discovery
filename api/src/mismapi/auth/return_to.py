"""Post-login `return_to` resolution via a route-key allowlist.

Client sends a route key (plus route's query string).
The server maps the key to a path it controls, so an
attacker can't steer a freshly authenticated user off-origin.
Unknown or missing keys fall back to the default landing path.

Keep `ROUTE_PATHS` in sync with the UI route table (`ui/app/routes.ts`).
Drift is safe-by-default: an unmapped key resolves to `DEFAULT_LANDING_PATH`.
"""

from __future__ import annotations

from urllib.parse import parse_qsl

from mismapi.utils import merge_query_params

DEFAULT_LANDING_PATH = "/"

ROUTE_PATHS: dict[str, str] = {
    "search": "/search",
    "runs": "/runs",
}


def resolve_return_to(route_key: str | None, query: str | None) -> str:
    """Resolve a client-supplied route key + query string to a safe local path."""
    path = ROUTE_PATHS.get(route_key or "")
    if path is None:
        return DEFAULT_LANDING_PATH
    if not query:
        return path
    return merge_query_params(path, dict(parse_qsl(query, keep_blank_values=True)))

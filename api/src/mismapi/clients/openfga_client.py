import logging
from typing import Any, cast

import httpx

from mismapi.core.errors import APIError
from mismapi.core.http_client import error_from_downstream_response

logger = logging.getLogger(__name__)


class OpenFGAClient:
    """HTTP client for the OpenFGA authorization model (MISM-291).

    Talks to a single OpenFGA store (``settings.openfga_store_id``) via its
    REST API. Used for platform-role checks (uploader/upload_reviewer/
    image_checker/executor) and per-resource relation tuples (owner,
    platform) — see Docs/OpenFGA/MISM-OpenFGA-Auth-Model.md.

    This client is a generic ``user``/``relation``/``object`` wrapper; it has
    no knowledge of ``AuthenticatedPrincipal`` or any application-level
    concept. Callers (e.g. ``RegistryService``) are responsible for mapping a
    principal to the ``user:<subject>`` tuple form before calling in, and for
    deciding what to do with the resulting authorization decision.
    """

    def __init__(
        self,
        base_url: str,
        store_id: str,
        authorization_model_id: str = "",
        timeout_seconds: float = 10.0,
    ) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout_seconds)
        self._store_id = store_id
        self._authorization_model_id = authorization_model_id

    async def check(self, *, user: str, relation: str, object_: str) -> bool:
        """Ask OpenFGA whether ``user`` has ``relation`` on ``object_``.

        e.g. ``check(user="user:alice", relation="uploader", object_="platform:main")``
        """
        body: dict[str, Any] = {
            "tuple_key": {"user": user, "relation": relation, "object": object_},
        }
        if self._authorization_model_id:
            body["authorization_model_id"] = self._authorization_model_id

        response = await self._post(f"/stores/{self._store_id}/check", body, action="check")
        allowed = response.get("allowed")
        if not isinstance(allowed, bool):
            raise APIError(
                status_code=502,
                code="openfga_check_invalid_response",
                detail="OpenFGA check response missing a boolean 'allowed' field.",
            )
        return allowed

    async def write_tuple(self, *, user: str, relation: str, object_: str) -> None:
        """Write a single relation tuple (e.g. grant a platform role or ownership)."""
        await self._write(writes=[{"user": user, "relation": relation, "object": object_}])

    async def delete_tuple(self, *, user: str, relation: str, object_: str) -> None:
        """Delete a single relation tuple (e.g. revoke a platform role)."""
        await self._write(deletes=[{"user": user, "relation": relation, "object": object_}])

    async def close(self) -> None:
        await self._client.aclose()

    # ── Internal ────────────────────────────────────────────────────

    async def _write(
        self,
        *,
        writes: list[dict[str, str]] | None = None,
        deletes: list[dict[str, str]] | None = None,
    ) -> None:
        body: dict[str, Any] = {}
        if writes:
            body["writes"] = {"tuple_keys": writes}
        if deletes:
            body["deletes"] = {"tuple_keys": deletes}
        if self._authorization_model_id:
            body["authorization_model_id"] = self._authorization_model_id

        await self._post(f"/stores/{self._store_id}/write", body, action="write")

    async def _post(self, url: str, json: dict[str, Any], action: str) -> dict[str, Any]:
        try:
            response = await self._client.post(url, json=json)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise APIError(
                status_code=504,
                code=f"openfga_{action}_timeout",
                detail=f"OpenFGA {action} timed out.",
            ) from exc
        except httpx.HTTPStatusError as exc:
            status, code, detail = error_from_downstream_response(
                exc.response,
                fallback_code=f"openfga_{action}_failed",
                fallback_detail=f"OpenFGA {action} call failed.",
            )
            raise APIError(status_code=status, code=code, detail=detail) from exc
        except httpx.HTTPError as exc:
            raise APIError(
                status_code=502,
                code=f"openfga_{action}_failed",
                detail=f"Failed to reach OpenFGA for {action}.",
            ) from exc

        try:
            return cast(dict[str, Any], response.json())
        except ValueError:
            return {}

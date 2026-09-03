import asyncio
import io
import logging
import re
import zipfile
from dataclasses import dataclass

import httpx
from pydantic import ValidationError

from mismapi.core.errors import APIError
from mismapi.core.http_client import error_from_downstream_response
from mismapi.schemas.biomodels import BioModelsRecordDTO, normalize_model_id

logger = logging.getLogger(__name__)

_DOWNLOAD_CHUNK_BYTES = 1024 * 1024

# The download redirects to
# ".../get-files/{submissionId}/{revision}/{submissionId}.{revision}.omex".
_REVISION_RE = re.compile(r"/get-files/[^/]+/([^/]+)/")


@dataclass(slots=True)
class BioModelsArchive:
    content: bytes
    # Upstream revision, or "" when the resolved URL doesn't expose one.
    revision: str
    resolved_url: str


class BioModelsClient:
    """HTTP client for the public BioModels repository API.

    Contract:
      - GET /{modelId}?format=json -> model metadata
      - GET /model/download/{modelId} -> 302 -> the OMEX (zip) archive

    There is no bulk endpoint, so `get_models` fans out one request per
    model id under a concurrency cap.
    """

    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float = 15.0,
        max_concurrency: int = 8,
        max_archive_bytes: int = 100 * 1024 * 1024,
        stub_upstream: bool = False,
    ) -> None:
        self._base_url = base_url
        self._max_concurrency = max_concurrency
        self._max_archive_bytes = max_archive_bytes
        self._stub_upstream = stub_upstream
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout_seconds,
            follow_redirects=True,
            headers={
                "Accept": "application/json",
                "User-Agent": "mism-discovery-gateway (+https://github.com/mism-center)",
            },
        )

    @property
    def configured(self) -> bool:
        return bool(self._base_url)

    def model_url(self, model_id: str) -> str:
        return f"{self._base_url}/{model_id}"

    # ── Single record ───────────────────────────────────────────────

    async def get_model(self, model_id: str) -> BioModelsRecordDTO:
        """GET /{modelId} -> metadata for one model."""
        if not self.configured:
            raise APIError(
                status_code=503,
                code="biomodels_not_configured",
                detail="BioModels integration is not configured. Set BIOMODELS_API_URL.",
            )

        normalized = normalize_model_id(model_id)
        if normalized is None:
            raise APIError(
                status_code=400,
                code="biomodels_invalid_model_id",
                detail=f"'{model_id}' is not a BioModels model id.",
            )

        try:
            response = await self._client.get(f"/{normalized}", params={"format": "json"})
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise APIError(
                status_code=504,
                code="biomodels_timeout",
                detail=f"BioModels timed out fetching {normalized}.",
            ) from exc
        except httpx.HTTPStatusError as exc:
            status, code, detail = error_from_downstream_response(
                exc.response,
                fallback_code="biomodels_fetch_failed",
                fallback_detail=f"BioModels failed to return {normalized}.",
            )
            raise APIError(status_code=status, code=code, detail=detail) from exc
        except httpx.HTTPError as exc:
            raise APIError(
                status_code=502,
                code="biomodels_fetch_failed",
                detail=f"Failed to reach BioModels for {normalized}.",
            ) from exc

        # A path BioModels doesn't recognize is not a 404: it 302s to the
        # site's login page, which then answers 200 with HTML. A success
        # status therefore proves nothing — the body has to parse.
        try:
            record = BioModelsRecordDTO.model_validate(response.json())
        except (ValueError, ValidationError) as exc:
            raise APIError(
                status_code=502,
                code="biomodels_invalid_response",
                detail=f"BioModels returned an unparseable record for {normalized}.",
            ) from exc

        return record.model_copy(
            update={"identifier": normalized, "url": self.model_url(normalized)}
        )

    # ── Archive download ────────────────────────────────────────────

    async def download_archive(self, model_id: str) -> BioModelsArchive:
        """Fetch a model's OMEX archive.

        ``GET /model/download/{modelId}`` redirects to a versioned path whose
        revision component is the only place the revision is exposed, so it is
        read back off the resolved URL.
        """
        if not self.configured:
            raise APIError(
                status_code=503,
                code="biomodels_not_configured",
                detail="BioModels integration is not configured. Set BIOMODELS_API_URL.",
            )

        normalized = normalize_model_id(model_id)
        if normalized is None:
            raise APIError(
                status_code=400,
                code="biomodels_invalid_model_id",
                detail=f"'{model_id}' is not a BioModels model id.",
            )

        if self._stub_upstream:
            logger.info("BioModels (stub) download_archive model_id=%s", normalized)
            return BioModelsArchive(
                content=_stub_archive(normalized),
                revision="1",
                resolved_url=f"stub://biomodels/{normalized}",
            )

        buf = io.BytesIO()
        try:
            async with self._client.stream(
                "GET",
                f"/model/download/{normalized}",
                # The shared client's flat timeout suits a JSON record; an
                # archive needs a long read budget with a short connect.
                timeout=httpx.Timeout(connect=10.0, read=120.0, write=None, pool=5.0),
                headers={"Accept": "application/zip, application/octet-stream, */*"},
            ) as response:
                if response.status_code == 404:
                    raise APIError(
                        status_code=404,
                        code="biomodels_model_not_found",
                        detail=f"BioModels has no downloadable archive for {normalized}.",
                    )
                if response.status_code >= 400:
                    raise APIError(
                        status_code=502,
                        code="biomodels_download_failed",
                        detail=(
                            f"BioModels returned HTTP {response.status_code} "
                            f"downloading {normalized}."
                        ),
                    )

                total = 0
                async for chunk in response.aiter_bytes(chunk_size=_DOWNLOAD_CHUNK_BYTES):
                    total += len(chunk)
                    if total > self._max_archive_bytes:
                        raise APIError(
                            status_code=413,
                            code="biomodels_archive_too_large",
                            detail=(
                                f"BioModels archive for {normalized} exceeds the "
                                f"{self._max_archive_bytes} byte limit."
                            ),
                        )
                    buf.write(chunk)

                resolved_url = str(response.url)
        except httpx.TimeoutException as exc:
            raise APIError(
                status_code=504,
                code="biomodels_download_timeout",
                detail=f"BioModels timed out downloading {normalized}.",
            ) from exc
        except httpx.HTTPError as exc:
            raise APIError(
                status_code=502,
                code="biomodels_download_failed",
                detail=f"Failed to download {normalized} from BioModels.",
            ) from exc

        content = buf.getvalue()
        # An unrecognized path can redirect to an HTML page answering 200, so a
        # success status does not prove the body is an archive.
        if not zipfile.is_zipfile(io.BytesIO(content)):
            raise APIError(
                status_code=502,
                code="biomodels_invalid_archive",
                detail=f"BioModels did not return a zip archive for {normalized}.",
            )

        match = _REVISION_RE.search(resolved_url)
        return BioModelsArchive(
            content=content,
            revision=match.group(1) if match else "",
            resolved_url=resolved_url,
        )

    # ── Bulk best-effort ────────────────────────────────────────────

    async def get_models(self, model_ids: list[str]) -> dict[str, BioModelsRecordDTO]:
        """Fetch many models concurrently, keyed by model id.

        Best-effort: an id BioModels cannot serve is logged and omitted
        from the result rather than failing the batch. Callers treat this
        metadata as additive, so a BioModels outage shouldn't break them.
        """
        if not self.configured or not model_ids:
            return {}

        wanted = sorted({normalized for a in model_ids if (normalized := normalize_model_id(a))})
        if not wanted:
            return {}

        limit = asyncio.Semaphore(self._max_concurrency)

        async def fetch(model_id: str) -> BioModelsRecordDTO | None:
            async with limit:
                try:
                    return await self.get_model(model_id)
                except APIError as exc:
                    logger.info(
                        "biomodels_fetch_skipped model_id=%s status=%s code=%s",
                        model_id,
                        exc.status_code,
                        exc.code,
                    )
                    return None

        records = await asyncio.gather(*(fetch(a) for a in wanted))
        return {r.identifier: r for r in records if r is not None}

    # ── Lifecycle ───────────────────────────────────────────────────

    async def close(self) -> None:
        await self._client.aclose()


def _stub_archive(model_id: str) -> bytes:
    """A minimal OMEX-shaped zip, so STUB_UPSTREAM_SERVICES needs no network."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            f"{model_id}.xml",
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<sbml xmlns="http://www.sbml.org/sbml/level2/version4" level="2" version="4">\n'
            f'  <model id="{model_id}" name="{model_id}"/>\n'
            "</sbml>\n",
        )
        zf.writestr(
            "manifest.xml",
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<omexManifest xmlns="http://identifiers.org/combine.specifications/omex-manifest">\n'
            f'  <content location="./{model_id}.xml" '
            'format="http://identifiers.org/combine.specifications/sbml"/>\n'
            "</omexManifest>\n",
        )
    return buf.getvalue()

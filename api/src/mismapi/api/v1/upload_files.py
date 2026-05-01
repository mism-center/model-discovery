import asyncio
import logging

import httpx
from fastapi import APIRouter, File, Request, UploadFile

from mismapi.clients.upload_client import UploadServiceClient
from mismapi.core.errors import APIError
from mismapi.core.settings import Settings
from mismapi.schemas.upload import UploadAcceptedResponse

logger = logging.getLogger(__name__)
router = APIRouter()
upload_file_body = File(...)


@router.post("/resources/{resource_id}/files", response_model=UploadAcceptedResponse)
async def upload_resource_file(
    request: Request,
    resource_id: str,
    file: UploadFile = upload_file_body,
) -> UploadAcceptedResponse:
    """Upload a file artifact for any resource (model, dataset, tool, …).

    The path is scoped by ``resource_id`` so the same flow handles every
    registry resource type. Upstream upload service still exposes its endpoint
    under ``/models/{id}``; we bridge the naming here without leaking it to
    callers.
    """
    settings: Settings = request.app.state.settings
    upload_client: UploadServiceClient = request.app.state.upload_client

    session = await upload_client.init_upload(
        resource_id=resource_id,
        filename=file.filename or "upload.bin",
        content_type=file.content_type,
    )

    total_bytes = 0
    part_number = 0
    while True:
        chunk = await file.read(settings.upload_chunk_size_bytes)
        if not chunk:
            break
        part_number += 1

        await _upload_part_with_retry(
            client=upload_client,
            upload_id=session.upload_id,
            part_number=part_number,
            chunk=chunk,
            max_attempts=settings.upload_retry_max_attempts,
            backoff_seconds=settings.upload_retry_backoff_seconds,
        )
        total_bytes += len(chunk)

    await upload_client.complete_upload(
        upload_id=session.upload_id,
        total_bytes=total_bytes,
        total_parts=part_number,
    )

    logger.info(
        "upload_accepted resource_id=%s upload_id=%s tracking_id=%s "
        "bytes_received=%s parts_uploaded=%s",
        resource_id,
        session.upload_id,
        session.tracking_id,
        total_bytes,
        part_number,
    )
    return UploadAcceptedResponse(
        resource_id=resource_id,
        upload_id=session.upload_id,
        tracking_id=session.tracking_id,
        filename=file.filename or "upload.bin",
        content_type=file.content_type,
        bytes_received=total_bytes,
        parts_uploaded=part_number,
    )


async def _upload_part_with_retry(
    client: UploadServiceClient,
    upload_id: str,
    part_number: int,
    chunk: bytes,
    max_attempts: int,
    backoff_seconds: float,
) -> None:
    for attempt in range(1, max_attempts + 1):
        try:
            if attempt == 1:
                await client.upload_part(upload_id=upload_id, part_number=part_number, chunk=chunk)
            else:
                logger.warning(
                    "upload_retry_part upload_id=%s part_number=%s attempt=%s",
                    upload_id,
                    part_number,
                    attempt,
                )
                await client.upload_part(upload_id=upload_id, part_number=part_number, chunk=chunk)
            return
        except httpx.HTTPStatusError as exc:
            if not _is_retryable_status(exc.response.status_code):
                raise APIError(
                    status_code=502,
                    code="upload_part_rejected",
                    detail="Upload service rejected a file chunk.",
                ) from exc
            if attempt == max_attempts:
                raise APIError(
                    status_code=502,
                    code="upload_part_retry_exhausted",
                    detail="Upload failed after exhausting retries.",
                ) from exc
        except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as exc:
            if attempt == max_attempts:
                raise APIError(
                    status_code=502,
                    code="upload_part_retry_exhausted",
                    detail="Upload failed after exhausting retries.",
                ) from exc

        await asyncio.sleep(backoff_seconds * attempt)


def _is_retryable_status(status_code: int) -> bool:
    return status_code == 429 or status_code >= 500

"""Local-disk replacement for ``UploadServiceClient``.

Used while no real upload service is deployed. Writes uploaded chunks
directly to the iRODS PVC mount that the download endpoint reads from, so
an upload becomes visible to GET /resources/{id}/files immediately on
completion.

Layout under the mount root:

    {mount}/{resource_id}/.uploads/{upload_id}.part   ← temp during upload
    {mount}/{resource_id}/{filename}                  ← atomic-renamed on complete

Speaks the same async protocol as ``UploadServiceClient``
(init_upload, upload_part, complete_upload, close) so the upload endpoint
doesn't care which backend is wired up.
"""

import asyncio
import logging
import os
import re
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import IO

from mismapi.clients.upload_client import UploadSession
from mismapi.core.errors import APIError

logger = logging.getLogger(__name__)

# Filenames are restricted to a conservative safe-name set. Real-world data
# files (datasets, artifacts) generally fit this; if it turns out to be too
# strict, widen the regex — don't reach for arbitrary unsanitized input.
_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")


@dataclass(slots=True)
class _LocalSession:
    """In-memory state for one in-flight upload."""

    resource_id: str
    filename: str
    target_path: Path
    temp_path: Path
    file: IO[bytes]
    tracking_id: str
    expected_part: int = 1
    bytes_written: int = 0


class LocalFileUploadClient:
    """Filesystem-backed upload client. Drop-in for ``UploadServiceClient``."""

    def __init__(self, mount_path: str, stub_upstream: bool = False) -> None:
        self._mount_root = Path(mount_path).resolve()
        self._stub_upstream = stub_upstream
        self._sessions: dict[str, _LocalSession] = {}

    # ── Public protocol (matches UploadServiceClient) ───────────────

    async def init_upload(
        self,
        resource_id: str,
        filename: str,
        content_type: str | None,
    ) -> UploadSession:
        if self._stub_upstream:
            logger.info(
                "Local upload client (stub) action=init_upload resource_id=%s filename=%s",
                resource_id,
                filename,
            )
            return UploadSession(
                upload_id=f"stub-upload-{secrets.token_hex(4)}",
                tracking_id=f"stub-track-{secrets.token_hex(4)}",
            )

        self._validate_resource_id(resource_id)
        safe_filename = self._sanitize_filename(filename)

        target_dir = (self._mount_root / resource_id).resolve()
        if not _is_relative_to(target_dir, self._mount_root):
            raise APIError(
                status_code=400,
                code="invalid_resource_id",
                detail="Resource id resolves outside the mount root.",
            )

        upload_id = f"local-{secrets.token_hex(8)}"
        tracking_id = f"track-{secrets.token_hex(8)}"
        temp_dir = target_dir / ".uploads"
        target_path = target_dir / safe_filename
        temp_path = temp_dir / f"{upload_id}.part"

        def _open() -> IO[bytes]:
            temp_dir.mkdir(parents=True, exist_ok=True)
            return temp_path.open("wb")

        try:
            handle = await asyncio.to_thread(_open)
        except OSError as exc:
            raise APIError(
                status_code=500,
                code="upload_init_failed",
                detail=f"Failed to create upload temp file: {exc}",
            ) from exc

        self._sessions[upload_id] = _LocalSession(
            resource_id=resource_id,
            filename=safe_filename,
            target_path=target_path,
            temp_path=temp_path,
            file=handle,
            tracking_id=tracking_id,
        )
        logger.info(
            "local_upload_init resource_id=%s upload_id=%s filename=%s content_type=%s",
            resource_id,
            upload_id,
            safe_filename,
            content_type,
        )
        return UploadSession(upload_id=upload_id, tracking_id=tracking_id)

    async def upload_part(self, upload_id: str, part_number: int, chunk: bytes) -> None:
        if self._stub_upstream:
            return

        session = self._sessions.get(upload_id)
        if session is None:
            raise APIError(
                status_code=404,
                code="upload_session_unknown",
                detail=f"Unknown upload session: {upload_id}",
            )
        # The gateway endpoint uploads in strict order. Reject out-of-order
        # parts — a real S3-style multipart impl would buffer them, but we
        # don't need that complexity here.
        if part_number != session.expected_part:
            raise APIError(
                status_code=400,
                code="upload_part_out_of_order",
                detail=(
                    f"Local upload backend requires in-order parts; "
                    f"expected {session.expected_part}, got {part_number}."
                ),
            )

        try:
            await asyncio.to_thread(session.file.write, chunk)
        except OSError as exc:
            raise APIError(
                status_code=500,
                code="upload_part_failed",
                detail=f"Failed to write upload chunk: {exc}",
            ) from exc

        session.expected_part += 1
        session.bytes_written += len(chunk)

    async def complete_upload(
        self,
        upload_id: str,
        total_bytes: int,
        total_parts: int,
    ) -> None:
        if self._stub_upstream:
            return

        session = self._sessions.pop(upload_id, None)
        if session is None:
            raise APIError(
                status_code=404,
                code="upload_session_unknown",
                detail=f"Unknown upload session: {upload_id}",
            )

        # Sanity check before promoting the file to its final name.
        if session.bytes_written != total_bytes:
            await asyncio.to_thread(session.file.close)
            await asyncio.to_thread(_safe_unlink, session.temp_path)
            raise APIError(
                status_code=400,
                code="upload_size_mismatch",
                detail=(
                    f"Reported total_bytes={total_bytes} does not match bytes "
                    f"written={session.bytes_written}."
                ),
            )

        try:
            await asyncio.to_thread(session.file.flush)
            # fsync the file so the bytes are durable before the rename;
            # atomic rename then exposes the file to readers.
            await asyncio.to_thread(os.fsync, session.file.fileno())
            await asyncio.to_thread(session.file.close)
            await asyncio.to_thread(os.replace, session.temp_path, session.target_path)
        except OSError as exc:
            raise APIError(
                status_code=500,
                code="upload_complete_failed",
                detail=f"Failed to finalize upload: {exc}",
            ) from exc

        logger.info(
            "local_upload_complete resource_id=%s filename=%s bytes=%s parts=%s",
            session.resource_id,
            session.filename,
            total_bytes,
            total_parts,
        )

    async def close(self) -> None:
        """Discard any in-flight sessions on shutdown."""
        for upload_id, session in list(self._sessions.items()):
            try:
                await asyncio.to_thread(session.file.close)
            except OSError:
                pass
            await asyncio.to_thread(_safe_unlink, session.temp_path)
            self._sessions.pop(upload_id, None)

    # ── Internal validation ────────────────────────────────────────

    @staticmethod
    def _validate_resource_id(resource_id: str) -> None:
        if not resource_id or "/" in resource_id or "\\" in resource_id or ".." in resource_id:
            raise APIError(
                status_code=400,
                code="invalid_resource_id",
                detail="resource_id must be non-empty and contain no path separators.",
            )

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        base = Path(filename).name  # strips any directory components
        if not base or not _SAFE_NAME_RE.match(base):
            raise APIError(
                status_code=400,
                code="invalid_filename",
                detail=(
                    f"Filename must contain only [A-Za-z0-9._-] and not be empty. Got: {filename!r}"
                ),
            )
        return base


def _is_relative_to(child: Path, parent: Path) -> bool:
    """Backport-shaped helper for ``Path.is_relative_to`` semantics."""
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass

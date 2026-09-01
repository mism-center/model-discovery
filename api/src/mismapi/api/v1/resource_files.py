"""Resource file listing and download endpoints.

Two routes, both keyed by resource_id:

  GET /resources/{id}/files            → JSON listing of all files in the
                                         resource's artifact directory.
  GET /resources/{id}/download         → Stream the directory as a zip.
  GET /resources/{id}/download?file=p  → Stream a single file at relative path p.

Path traversal protection lives in ``core/file_storage.py``; this router only
shapes responses.
"""

import io
import logging
import mimetypes
import re
import zipfile
from collections.abc import Buffer, Iterator
from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse, StreamingResponse
from mism_registry.resource import Resource

from mismapi.auth.base import OptionalPrincipalDep
from mismapi.core.deps import RegistryServiceDep
from mismapi.schemas.registry import ResourceFileItem, ResourceFilesResponse

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Helpers ─────────────────────────────────────────────────────


_PLACEHOLDER_NAMES: frozenset[str] = frozenset({".gitignore", ".gitkeep", ".keep"})


def _walk_files(root: Path) -> list[ResourceFileItem]:
    """Recursively list every regular file under ``root``.

    Directories themselves are skipped — listings are file-centric. Symlinks
    are followed only if they point inside the root (the underlying iRODS
    mount uses POSIX semantics, so this is fine).

    Git/filesystem placeholder files (``.gitignore``, ``.gitkeep``, ``.keep``)
    are excluded so they never surface in resource or annotation output listings.
    """
    items: list[ResourceFileItem] = []
    for entry in sorted(root.rglob("*")):
        if not entry.is_file():
            continue
        if entry.name in _PLACEHOLDER_NAMES:
            continue
        try:
            rel = entry.relative_to(root)
        except ValueError:
            # Symlink pointing outside root — skip silently.
            continue
        stat = entry.stat()
        items.append(
            ResourceFileItem(
                path=str(rel).replace("\\", "/"),
                name=entry.name,
                size_bytes=stat.st_size,
                is_dir=False,
                modified_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
            )
        )
    return items


_ZIP_READ_CHUNK = 64 * 1024  # 64 KiB — balances syscalls vs. memory.


class _StreamingBuffer(io.RawIOBase):
    """Write-only, non-seekable buffer that ZipFile streams data into.

    ``zipfile.ZipFile`` checks ``seekable()`` and switches to data-descriptor
    mode (size/CRC written *after* each member) when the stream is non-seekable
    — exactly what we need for true streaming zip output.
    """

    def __init__(self) -> None:
        super().__init__()
        self._buffer = bytearray()
        self._pos = 0  # virtual position; needed because ZipFile calls tell()

    def writable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return False

    def write(self, data: Buffer) -> int:
        view = memoryview(data)
        n = view.nbytes
        self._buffer.extend(view)
        self._pos += n
        return n

    def tell(self) -> int:
        return self._pos

    def consume(self) -> bytes:
        """Drain everything ZipFile has written so far and hand it to the response."""
        chunk = bytes(self._buffer)
        self._buffer.clear()
        return chunk


def _zip_directory_stream(directory: Path) -> Iterator[bytes]:
    """Yield the zip of ``directory`` as a stream of chunks.

    Memory bound is roughly one ``_ZIP_READ_CHUNK`` plus a single member's
    compression buffer — independent of total artifact size or file count.
    Works for multi-GB datasets without OOM.
    """
    buf = _StreamingBuffer()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for entry in directory.rglob("*"):
            if not entry.is_file():
                continue
            arcname = str(entry.relative_to(directory)).replace("\\", "/")
            # force_zip64=True handles members >4 GiB and side-steps a
            # seek-back-to-fix-header path that would break streaming.
            with zf.open(arcname, mode="w", force_zip64=True) as zentry:
                with entry.open("rb") as src:
                    while chunk := src.read(_ZIP_READ_CHUNK):
                        zentry.write(chunk)
                        if pending := buf.consume():
                            yield pending
            if pending := buf.consume():
                yield pending
    # ZipFile.__exit__ writes the central directory — emit those last bytes.
    if tail := buf.consume():
        yield tail


_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")
_REPEATED_HYPHENS = re.compile(r"-{2,}")
_MAX_ZIP_STEM = 100


def _filename_slug(value: str) -> str:
    """Reduce ``value`` to characters that are safe and legible in a filename.

    Everything outside ``[A-Za-z0-9._-]`` collapses to a single hyphen. That is
    mostly cosmetic — model names carry spaces, slashes and punctuation that
    read badly in a Downloads folder — but it also keeps the result ASCII,
    which Content-Disposition needs: a raw non-ASCII filename either reaches the
    browser mis-decoded as latin-1 or blows up Starlette's header encoding.
    """
    slug = _UNSAFE_FILENAME_CHARS.sub("-", value)
    return _REPEATED_HYPHENS.sub("-", slug).strip("-._")


def _zip_filename(resource: Resource) -> str:
    """Name the archive after the resource and its version, not its id.

    Ids are usually UUIDs, which tell the person who downloaded the zip nothing
    about what is in it. ``name`` is required on a Resource and ``version`` is
    optional, so "Immune Model" 1.2 gives ``Immune-Model-1.2.zip``.

    Name and version are slugged separately so a name that survives slugging
    empty-handed (one written entirely in a non-Latin script, say) falls back to
    the id instead of leaving a filename that is nothing but a version number.
    """
    name = _filename_slug(resource.name) or _filename_slug(resource.id) or "download"
    version = _filename_slug(resource.version)
    stem = f"{name}-{version}" if version else name
    return f"{stem[:_MAX_ZIP_STEM].strip('-._')}.zip"


def _attachment_disposition(filename: str) -> str:
    """Build a Content-Disposition header value for ``filename``.

    Delegated to the stdlib's header machinery instead of f-stringing the name
    into the value: it applies RFC 2045 quoting and rejects linefeeds, so a
    resource name can never break out of the header. ``_zip_filename`` already
    restricts the character set; this is the layer that makes that a
    presentation concern rather than the only thing standing between a model
    name and response-splitting.
    """
    message = EmailMessage()
    message["Content-Disposition"] = "attachment"
    message.set_param("filename", filename, header="Content-Disposition")
    return str(message["Content-Disposition"])


# ── GET /resources/{id}/files ───────────────────────────────────


@router.get("/resources/{resource_id}/files", response_model=ResourceFilesResponse)
async def list_resource_files(
    resource_id: str,
    service: RegistryServiceDep,
    principal: OptionalPrincipalDep,
) -> ResourceFilesResponse:
    """List every file in the resource's artifact directory.

    A resource with no directory on the mount yet returns an empty list, not a
    404 — see ``RegistryService.find_resource_directory``.

    Visibility-gated the same way as ``GET /models/{model_id}``: not-yet-public
    resources are only listable by their owner (404, not 403 — avoids an id
    oracle for resources the caller may not know exist).
    """
    resource, directory = service.find_resource_directory(resource_id)
    await service.assert_can_view_model(principal, resource=resource)
    files = [] if directory is None else _walk_files(directory)
    return ResourceFilesResponse(
        resource_id=resource.id,
        location_uri=resource.location_uri,
        files=files,
        total=len(files),
    )


# ── GET /resources/{id}/download ────────────────────────────────


@router.get("/resources/{resource_id}/download", response_model=None)
async def download_resource(
    resource_id: str,
    service: RegistryServiceDep,
    principal: OptionalPrincipalDep,
    file: str | None = Query(
        default=None,
        description=(
            "Relative path to a single file inside the resource directory. "
            "Omit to download the entire directory as a zip archive."
        ),
    ),
    disposition: str = Query(
        default="attachment",
        pattern="^(attachment|inline)$",
        description=(
            "How a single file is served. 'attachment' (default) forces a "
            "download; 'inline' serves it with a content type guessed from the "
            "extension so the browser can render it (used for in-app previews). "
            "Ignored for the zip archive."
        ),
    ),
) -> StreamingResponse | FileResponse:
    """Download artifacts for a resource — single file or whole directory zip.

    Visibility-gated the same way as ``GET /models/{model_id}``: not-yet-public
    resources are only downloadable by their owner (404, not 403).
    """
    if file is not None:
        resource, file_path = service.resolve_resource_file(resource_id, file)
        await service.assert_can_view_model(principal, resource=resource)
        logger.info("Serving file %s for resource %s (%s)", file, resource.id, disposition)
        if disposition == "inline":
            # Guess the type from the extension so browsers render images/text
            # inline. `content_disposition_type="inline"` keeps the filename
            # (for "save as") without forcing a download.
            media_type, _ = mimetypes.guess_type(file_path.name)
            return FileResponse(
                path=str(file_path),
                filename=file_path.name,
                media_type=media_type or "application/octet-stream",
                content_disposition_type="inline",
            )
        return FileResponse(
            path=str(file_path),
            filename=file_path.name,
            media_type="application/octet-stream",
        )

    resource, directory = service.get_resource_directory(resource_id)
    await service.assert_can_view_model(principal, resource=resource)
    logger.info("Streaming zip of %s for resource %s", directory, resource.id)
    return StreamingResponse(
        _zip_directory_stream(directory),
        media_type="application/zip",
        headers={"Content-Disposition": _attachment_disposition(_zip_filename(resource))},
    )

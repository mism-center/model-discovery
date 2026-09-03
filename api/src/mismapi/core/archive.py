"""Extract downloaded archives into a resource's working tree.

Each member is resolved against the destination root and skipped if it lands
outside it. The ``.resolve()`` is load-bearing: ``..`` segments are not
normalized lexically, so ``dest/../escape.txt`` *is* considered relative to
``dest`` until the path is resolved.

Members are written with ``write_bytes``, so a member carrying symlink mode
bits lands as a regular file holding its target path — it cannot redirect a
later write outside the destination.
"""

from __future__ import annotations

import io
import logging
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

from mismapi.core.errors import APIError

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ExtractedArchive:
    file_count: int
    total_bytes: int


def extract_zip(
    buf: io.BytesIO,
    dest_dir: Path,
    *,
    max_total_bytes: int,
    strip_root_dir: bool = False,
) -> ExtractedArchive:
    """Extract a zip archive into *dest_dir*.

    Arguments are as for ``extract_tarball``.
    """
    try:
        with zipfile.ZipFile(buf) as zf:
            infos = [info for info in zf.infolist() if not info.is_dir()]
            names = [info.filename for info in infos]
            _reject_oversized(sum(info.file_size for info in infos), max_total_bytes)

            prefix = _root_dir(names) if strip_root_dir else ""
            dest_dir.mkdir(parents=True, exist_ok=True)

            count = total = 0
            for info in infos:
                dest_path = _safe_dest(dest_dir, info.filename, prefix)
                if dest_path is None:
                    continue
                data = zf.read(info)
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                dest_path.write_bytes(data)
                count += 1
                total += len(data)

            return ExtractedArchive(file_count=count, total_bytes=total)
    except zipfile.BadZipFile as exc:
        raise _corrupt_archive(exc) from exc


def extract_tarball(
    buf: io.BytesIO,
    dest_dir: Path,
    *,
    max_total_bytes: int,
    strip_root_dir: bool = False,
) -> ExtractedArchive:
    """Extract a gzipped tarball into *dest_dir*.

    ``max_total_bytes`` bounds the summed uncompressed size the archive
    declares; over it, nothing is written.

    ``strip_root_dir`` drops the leading path component when — and only when —
    every member shares one, so an archive that wraps its contents in a single
    directory unpacks flat. Archives naming members at the root, or with
    several top-level entries, are unaffected.
    """
    try:
        with tarfile.open(fileobj=buf, mode="r:gz") as tf:
            members = [member for member in tf.getmembers() if not member.isdir()]
            _reject_oversized(sum(member.size for member in members), max_total_bytes)

            prefix = _root_dir([member.name for member in members]) if strip_root_dir else ""
            dest_dir.mkdir(parents=True, exist_ok=True)

            count = total = 0
            for member in members:
                dest_path = _safe_dest(dest_dir, member.name, prefix)
                if dest_path is None:
                    continue
                src = tf.extractfile(member)
                if src is None:  # not a readable regular file
                    continue
                data = src.read()
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                dest_path.write_bytes(data)
                count += 1
                total += len(data)

            return ExtractedArchive(file_count=count, total_bytes=total)
    except tarfile.TarError as exc:
        raise _corrupt_archive(exc) from exc


def _safe_dest(dest_dir: Path, name: str, prefix: str) -> Path | None:
    """Where *name* should be written, or None if it escapes *dest_dir*."""
    stripped = name.removeprefix(prefix)
    if not stripped:
        return None

    dest_root = dest_dir.resolve()
    dest_path = (dest_root / stripped).resolve()
    if not dest_path.is_relative_to(dest_root):
        logger.warning("archive_member_skipped name=%s reason=path_traversal", name)
        return None
    return dest_path


def _root_dir(names: list[str]) -> str:
    """The one top-level directory every member sits under, or ``""``."""
    roots = set()
    for name in names:
        head, separator, _ = name.partition("/")
        if not separator:
            return ""
        roots.add(head)
    return f"{roots.pop()}/" if len(roots) == 1 else ""


def _reject_oversized(declared_bytes: int, max_total_bytes: int) -> None:
    # Both formats record uncompressed sizes up front, so an oversized archive
    # is rejected before anything is written. Neither reader yields more than
    # the declared size for a member, so this bound holds for headers that
    # understate: they truncate and fail their integrity check instead.
    if declared_bytes > max_total_bytes:
        raise APIError(
            status_code=413,
            code="archive_too_large",
            detail=(
                f"Archive declares {declared_bytes} bytes, "
                f"exceeding the {max_total_bytes} byte limit."
            ),
        )


def _corrupt_archive(exc: Exception) -> APIError:
    return APIError(
        status_code=502,
        code="invalid_archive",
        detail=f"Archive is corrupt or unreadable: {exc}",
    )

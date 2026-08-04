"""Resolve resource location_uris to on-pod filesystem paths.

The gateway has the iRODS PVC mounted (see chart values.yaml). A resource's
``location_uri`` looks like one of:

    irods:///datasets/abc-123          # canonical form (3 slashes = empty host)
    irods://datasets/abc-123           # tolerated; first segment is *not* a host
    /irods/datasets/abc-123            # absolute path that already includes the mount
    /datasets/abc-123                  # plain absolute path — implicit iRODS
    datasets/abc-123                   # plain relative path — implicit iRODS

All five resolve to ``{irods_mount_path}/datasets/abc-123`` on disk. Any path
without an explicit scheme is interpreted as iRODS-mounted.

This module is the single place that mediates the URI-to-disk translation,
which means it's also the single place that enforces:

  * Only iRODS-mounted resources are accepted (other schemes 400).
  * The resolved path stays inside the mount root — no ``..`` escapes.
  * The resolved path actually exists.

``validate_location_uri`` exposes the same scheme contract to API request
schemas so unsupported schemes (``http://``, ``s3://``, etc.) are rejected at
create/update time rather than only at download time.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from mismapi.core.errors import APIError

_LocationUriKind = Literal["irods", "path"]


def _classify_location_uri(location_uri: str) -> _LocationUriKind:
    """Return the scheme kind of ``location_uri`` or raise ``ValueError``.

    The accepted shapes are:

      * ``irods://...`` and ``irods:///...`` — explicit iRODS scheme
      * scheme-less paths (absolute or relative) — implicit iRODS

    Anything else (``http://``, ``https://``, ``s3://``, ``docker://``,
    ``git+https://``, ...) is rejected because the download endpoint cannot
    resolve it. Used by both ``resolve_location_uri`` and the API request
    validators so the create-time contract matches the download-time contract.
    """
    # Note: on Windows, `urlsplit("C:\\foo")` returns scheme="c" because the
    # drive letter looks like a URL scheme. Detect that case explicitly so
    # plain absolute paths still take the implicit-iRODS branch.
    parts = urlsplit(location_uri)
    is_plain_path = parts.scheme == "" or (len(parts.scheme) == 1 and parts.scheme.isalpha())
    if parts.scheme == "irods":
        return "irods"
    if is_plain_path:
        return "path"
    raise ValueError(
        f"Unsupported location_uri scheme '{parts.scheme}'. "
        "location_uri must use the 'irods://' scheme or be a path (relative or absolute); "
        "the download endpoint cannot resolve other schemes."
    )


def validate_location_uri(location_uri: str) -> str:
    """Validate the scheme of a user-supplied ``location_uri``.

    Returns the input unchanged when valid. Empty strings are accepted so
    callers can create a resource without committing to a path up front — the
    tus ``post-finish`` hook stamps a real iRODS URI once an upload completes.
    Raises ``ValueError`` on unsupported schemes so Pydantic surfaces a 4xx.
    """
    if not location_uri:
        return location_uri
    _classify_location_uri(location_uri)
    return location_uri


def resolve_location_uri(location_uri: str, mount_path: str, *, missing_ok: bool = False) -> Path:
    """Translate a resource ``location_uri`` to an absolute on-disk Path.

    Raises APIError(400) for unsupported schemes or paths that escape the mount.
    Raises APIError(404) if the resolved directory doesn't exist on disk, unless
    ``missing_ok`` — the traversal check above still applies either way, so a
    tolerated absence never widens what a caller can address.
    """
    if not location_uri:
        raise APIError(
            status_code=400,
            code="invalid_location_uri",
            detail="Resource has no location_uri.",
        )

    mount_root = Path(mount_path).resolve()

    # 1. Extract the path component, scheme-aware.
    try:
        kind = _classify_location_uri(location_uri)
    except ValueError as exc:
        raise APIError(
            status_code=400,
            code="unsupported_location_scheme",
            detail=str(exc),
        ) from exc

    parts = urlsplit(location_uri)
    if kind == "irods":
        # urlsplit("irods:///foo/bar") -> path="/foo/bar"
        # urlsplit("irods://foo/bar")  -> netloc="foo", path="/bar"  ← treat netloc as first segment
        rel = (parts.netloc + parts.path).lstrip("/")
    else:
        # Plain path (no scheme, or single-letter Windows drive) → implicit iRODS.
        # Strip the mount prefix if present so "/irods/foo/bar", "/foo/bar",
        # and "foo/bar" all collapse to the same relative path under mount_root.
        if location_uri.startswith(mount_path):
            rel = location_uri[len(mount_path) :].lstrip("/").lstrip("\\")
        else:
            rel = location_uri.lstrip("/").lstrip("\\")

    # 2. Resolve and validate it stays inside the mount.
    candidate = (mount_root / rel).resolve()
    if not candidate.is_relative_to(mount_root):
        raise APIError(
            status_code=400,
            code="path_traversal_blocked",
            detail="Resolved path escapes the storage mount.",
        )

    # 3. Existence check (the registry knows about resources we never wrote).
    if not candidate.exists() and not missing_ok:
        raise APIError(
            status_code=404,
            code="resource_files_not_found",
            detail=f"No files found on disk for resource at {location_uri}.",
        )

    return candidate


def safe_join(base: Path, rel_path: str) -> Path:
    """Join ``rel_path`` onto ``base``, refusing any escape via '..' or absolutes.

    Used by the download-single-file endpoint, where the client supplies the
    relative path. Mirrors the traversal check from ``resolve_location_uri``.
    """
    if not rel_path:
        raise APIError(
            status_code=400,
            code="invalid_file_path",
            detail="File path must not be empty.",
        )

    base_resolved = base.resolve()
    candidate = (base_resolved / rel_path).resolve()

    if not candidate.is_relative_to(base_resolved):
        raise APIError(
            status_code=400,
            code="path_traversal_blocked",
            detail="File path escapes the resource directory.",
        )

    if not candidate.exists():
        raise APIError(
            status_code=404,
            code="file_not_found",
            detail=f"File '{rel_path}' not found in resource directory.",
        )

    if not candidate.is_file():
        raise APIError(
            status_code=400,
            code="not_a_file",
            detail=f"Path '{rel_path}' is not a regular file.",
        )

    return candidate

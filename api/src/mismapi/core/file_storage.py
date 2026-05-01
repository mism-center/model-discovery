"""Resolve resource location_uris to on-pod filesystem paths.

The gateway has the iRODS PVC mounted (see chart values.yaml). A resource's
``location_uri`` looks like one of:

    irods:///datasets/abc-123          # canonical form (3 slashes = empty host)
    irods://datasets/abc-123           # tolerated; first segment is *not* a host
    /irods/datasets/abc-123            # plain absolute path under the mount

All three resolve to ``{irods_mount_path}/datasets/abc-123`` on disk.

This module is the single place that mediates the URI-to-disk translation,
which means it's also the single place that enforces:

  * Only ``irods://...`` (or paths under the mount) are accepted.
  * The resolved path stays inside the mount root — no ``..`` escapes.
  * The resolved path actually exists.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

from mismapi.core.errors import APIError


def resolve_location_uri(location_uri: str, mount_path: str) -> Path:
    """Translate a resource ``location_uri`` to an absolute on-disk Path.

    Raises APIError(400) for unsupported schemes or paths that escape the mount.
    Raises APIError(404) if the resolved directory doesn't exist on disk.
    """
    if not location_uri:
        raise APIError(
            status_code=400,
            code="invalid_location_uri",
            detail="Resource has no location_uri.",
        )

    mount_root = Path(mount_path).resolve()

    # 1. Extract the path component, scheme-aware.
    parts = urlsplit(location_uri)
    if parts.scheme == "irods":
        # urlsplit("irods:///foo/bar") -> path="/foo/bar"
        # urlsplit("irods://foo/bar")  -> netloc="foo", path="/bar"  ← treat netloc as first segment
        rel = (parts.netloc + parts.path).lstrip("/")
    elif parts.scheme == "" and location_uri.startswith(mount_path):
        # Plain "/irods/foo/bar" — strip the mount prefix.
        rel = location_uri[len(mount_path) :].lstrip("/")
    else:
        raise APIError(
            status_code=400,
            code="unsupported_location_scheme",
            detail=(
                f"Cannot serve files for scheme '{parts.scheme or 'plain-path'}'. "
                "Only iRODS-mounted resources are downloadable."
            ),
        )

    # 2. Resolve and validate it stays inside the mount.
    candidate = (mount_root / rel).resolve()
    if not candidate.is_relative_to(mount_root):
        raise APIError(
            status_code=400,
            code="path_traversal_blocked",
            detail="Resolved path escapes the storage mount.",
        )

    # 3. Existence check (the registry knows about resources we never wrote).
    if not candidate.exists():
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

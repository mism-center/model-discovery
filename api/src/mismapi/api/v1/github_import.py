"""GitHub repository import endpoint.

Downloads a tarball of the requested branch from the GitHub API and extracts
each file directly into ``IRODS_MOUNT_PATH/<model_id>/``.  No archive is
written to disk — the ``.tar.gz`` is streamed into memory, extracted via
Python's built-in ``tarfile`` module, and individual working-tree files are
written to the iRODS PVC.  After a successful extract the endpoint creates an
annotation run via the Execution service.
"""

from __future__ import annotations

import asyncio
import io
import logging
import re
import tarfile
from pathlib import Path

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, field_validator

from mismapi.auth.base import AuthenticatedPrincipalDep
from mismapi.core.deps import RegistryServiceDep, SettingsDep
from mismapi.core.errors import APIError
from mismapi.utils import upload_dir

logger = logging.getLogger(__name__)

router = APIRouter()

# Matches:
#   https://github.com/owner/repo
#   https://github.com/owner/repo.git
#   https://github.com/owner/repo/
#   https://github.com/owner/repo/tree/branch-name
_GITHUB_URL_RE = re.compile(
    r"https?://github\.com"
    r"/(?P<owner>[^/]+)"
    r"/(?P<repo>[^/]+?)"
    r"(?:\.git)?"  # optional .git suffix
    r"(?:/tree/(?P<branch>[^/?#]+))?"
    r"/?$"
)

_GITHUB_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "mism-discovery/1.0",
}


class GitHubImportRequest(BaseModel):
    """Request body for importing a GitHub repository."""

    github_url: str
    """Public GitHub repository URL.

    Accepted forms:
    * ``https://github.com/owner/repo``
    * ``https://github.com/owner/repo.git``
    * ``https://github.com/owner/repo/tree/branch``

    The branch embedded in the URL takes precedence over the ``branch`` field.
    When neither is supplied the repository's default branch is detected
    automatically via the GitHub API.
    """

    branch: str | None = None
    """Branch to download.  ``None`` (the default) auto-detects the
    repository's default branch from the GitHub API."""

    @field_validator("github_url")
    @classmethod
    def validate_github_url(cls, v: str) -> str:
        """Reject URLs that are not a recognisable GitHub repository path."""
        if not _GITHUB_URL_RE.match(v.strip()):
            raise ValueError(
                "github_url must be a GitHub repository URL "
                "(e.g. https://github.com/owner/repo or "
                "https://github.com/owner/repo/tree/branch)"
            )
        return v.strip()


class GitHubImportResponse(BaseModel):
    """Response returned once the repository has been extracted into iRODS."""

    model_id: str
    branch: str
    files_extracted: int
    size_bytes: int
    location_uri: str


async def _get_default_branch(client: httpx.AsyncClient, owner: str, repo: str) -> str:
    """Return the repository's default branch name via the GitHub REST API."""
    resp = await client.get(
        f"https://api.github.com/repos/{owner}/{repo}",
        headers=_GITHUB_HEADERS,
    )
    if resp.status_code == 404:
        raise APIError(
            status_code=404,
            code="github_repo_not_found",
            detail=f"GitHub repository '{owner}/{repo}' not found. "
            "Check that the repository is public.",
        )
    if resp.status_code == 403:
        raise APIError(
            status_code=502,
            code="github_access_denied",
            detail=f"GitHub returned 403 for '{owner}/{repo}'. "
            "The repository may be private or rate-limited.",
        )
    if resp.status_code >= 400:
        raise APIError(
            status_code=502,
            code="github_api_error",
            detail=f"GitHub API returned HTTP {resp.status_code} for '{owner}/{repo}'.",
        )
    data: dict[str, object] = resp.json()
    default_branch = data.get("default_branch")
    return str(default_branch) if default_branch else "main"


def _is_relative_to(child: Path, parent: Path) -> bool:
    """Return True if *child* is inside *parent* (path-traversal guard)."""
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _extract_tarball(buf: io.BytesIO, dest_dir: Path) -> tuple[int, int]:
    """Extract a GitHub ``.tar.gz`` tarball into *dest_dir*.

    GitHub tarballs always have a single top-level directory named
    ``{owner}-{repo}-{sha}/``.  That component is stripped so files land
    directly under *dest_dir*.

    Returns ``(files_extracted, total_bytes)``.
    """
    count = total = 0
    dest_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=buf, mode="r:gz") as tf:
        for member in tf.getmembers():
            # Strip the leading "{owner}-{repo}-{sha}/" component.
            slash = member.name.find("/")
            if slash == -1:
                continue
            stripped = member.name[slash + 1 :]
            if not stripped or member.isdir():
                continue
            dest_path = (dest_dir / stripped).resolve()
            if not _is_relative_to(dest_path, dest_dir.resolve()):
                continue  # path-traversal guard
            src = tf.extractfile(member)
            if src is None:
                continue
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            data = src.read()
            dest_path.write_bytes(data)
            count += 1
            total += len(data)
    return count, total


@router.post(
    "/models/{model_id}/github-import",
    response_model=GitHubImportResponse,
    status_code=201,
    summary="Extract a GitHub repository tarball into iRODS and trigger annotation",
)
async def import_from_github(
    model_id: str,
    body: GitHubImportRequest,
    service: RegistryServiceDep,
    settings: SettingsDep,
    principal: AuthenticatedPrincipalDep,
) -> GitHubImportResponse:
    """Download a GitHub repository tarball and extract files into ``IRODS_MOUNT_PATH/{model_id}/``.

    Steps:
    1. Verify the calling user owns the model.
    2. Parse the GitHub URL (strip ``.git``, extract owner/repo/branch).
    3. Auto-detect the default branch when none is specified.
    4. Stream the ``.tar.gz`` from ``api.github.com`` into memory, then
       extract each file directly into the iRODS PVC directory.
    5. Call ``mark_upload_complete`` to update ``location_uri`` and
       ``upload_status`` in the registry.

    Annotation is initiated separately via ``POST /models/{model_id}/runs``.
    """
    # 1. Ownership check — raises APIError(403) if principal is not the owner.
    resource = service.get_resource_and_assert_ownership(principal, resource_id=model_id)

    # 2. Parse GitHub URL.
    m = _GITHUB_URL_RE.match(body.github_url)
    assert m is not None  # noqa: S101 — validator guarantees a match
    owner: str = m.group("owner")
    repo: str = m.group("repo")  # .git already excluded by the regex
    branch_from_url: str | None = m.group("branch")

    branch = ""
    files_extracted = 0
    total_bytes = 0
    dest_dir = (
        Path(settings.irods_mount_path) / upload_dir(resource.id, resource.version)
    ).resolve()
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(connect=10.0, read=120.0, write=None, pool=5.0),
        ) as client:
            # 3. Resolve branch: URL > explicit field > auto-detect via GitHub API.
            if branch_from_url:
                branch = branch_from_url
            elif body.branch:
                branch = body.branch
            else:
                branch = await _get_default_branch(client, owner, repo)

            tarball_url = f"https://api.github.com/repos/{owner}/{repo}/tarball/{branch}"

            logger.info(
                "github_import model=%s owner=%s repo=%s branch=%s dest=%s",
                model_id,
                owner,
                repo,
                branch,
                dest_dir,
            )

            # 4. Stream tarball into memory then extract to iRODS directory.
            async with client.stream("GET", tarball_url, headers=_GITHUB_HEADERS) as resp:
                if resp.status_code == 404:
                    raise APIError(
                        status_code=404,
                        code="github_repo_not_found",
                        detail=(
                            f"GitHub repository '{owner}/{repo}' branch '{branch}' not found. "
                            "Check that the repository is public and the branch name is correct."
                        ),
                    )
                if resp.status_code == 403:
                    raise APIError(
                        status_code=502,
                        code="github_access_denied",
                        detail=(
                            f"GitHub returned 403 for '{owner}/{repo}'. "
                            "The repository may be private or rate-limited."
                        ),
                    )
                if resp.status_code >= 400:
                    raise APIError(
                        status_code=502,
                        code="github_download_failed",
                        detail=f"GitHub returned HTTP {resp.status_code} for '{owner}/{repo}'.",
                    )

                buf = io.BytesIO()
                async for chunk in resp.aiter_bytes(chunk_size=settings.upload_chunk_size_bytes):
                    buf.write(chunk)
                buf.seek(0)

            files_extracted, total_bytes = await asyncio.to_thread(_extract_tarball, buf, dest_dir)

    except httpx.TimeoutException as exc:
        raise APIError(
            status_code=504,
            code="github_download_timeout",
            detail=f"Timed out downloading '{owner}/{repo}' from GitHub.",
        ) from exc
    except httpx.RequestError as exc:
        raise APIError(
            status_code=502,
            code="github_download_error",
            detail=f"Network error while downloading '{owner}/{repo}': {exc}",
        ) from exc

    logger.info(
        "github_import_complete model=%s branch=%s files=%d bytes=%d",
        model_id,
        branch,
        files_extracted,
        total_bytes,
    )

    # 5. Mark upload complete — stamps location_uri and upload_status in registry.
    updated = service.mark_upload_complete(principal, resource_id=model_id)

    return GitHubImportResponse(
        model_id=model_id,
        branch=branch,
        files_extracted=files_extracted,
        size_bytes=total_bytes,
        location_uri=updated.location_uri,
    )

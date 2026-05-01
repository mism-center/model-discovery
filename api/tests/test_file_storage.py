"""Unit tests for core/file_storage URI resolution + traversal guards."""

from pathlib import Path

import pytest

from mismapi.core.errors import APIError
from mismapi.core.file_storage import resolve_location_uri, safe_join


@pytest.fixture
def mount(tmp_path: Path) -> Path:
    """A throwaway iRODS-mount-shaped directory tree."""
    (tmp_path / "datasets" / "abc-123").mkdir(parents=True)
    (tmp_path / "datasets" / "abc-123" / "file.csv").write_text("a,b\n1,2\n")
    return tmp_path


# ── resolve_location_uri ────────────────────────────────────────


def test_resolve_irods_triple_slash(mount: Path) -> None:
    uri = "irods:///datasets/abc-123"
    assert resolve_location_uri(uri, str(mount)) == (mount / "datasets" / "abc-123").resolve()


def test_resolve_irods_double_slash_treats_netloc_as_segment(mount: Path) -> None:
    """irods://datasets/abc-123 — urlsplit puts 'datasets' in netloc; we recover it."""
    uri = "irods://datasets/abc-123"
    assert resolve_location_uri(uri, str(mount)) == (mount / "datasets" / "abc-123").resolve()


def test_resolve_plain_mount_path(mount: Path) -> None:
    uri = f"{mount}/datasets/abc-123"
    assert resolve_location_uri(uri, str(mount)) == (mount / "datasets" / "abc-123").resolve()


def test_resolve_plain_absolute_path_implicit_irods(mount: Path) -> None:
    """A scheme-less absolute path (not under mount) is treated as iRODS-relative."""
    uri = "/datasets/abc-123"
    assert resolve_location_uri(uri, str(mount)) == (mount / "datasets" / "abc-123").resolve()


def test_resolve_plain_relative_path_implicit_irods(mount: Path) -> None:
    """A scheme-less relative path is treated as iRODS-relative."""
    uri = "datasets/abc-123"
    assert resolve_location_uri(uri, str(mount)) == (mount / "datasets" / "abc-123").resolve()


def test_resolve_unsupported_scheme_400(mount: Path) -> None:
    with pytest.raises(APIError) as exc:
        resolve_location_uri("s3://bucket/key", str(mount))
    assert exc.value.status_code == 400
    assert exc.value.code == "unsupported_location_scheme"


def test_resolve_git_scheme_400(mount: Path) -> None:
    """Sanity: schemes other than irods are rejected even though they look path-ish."""
    with pytest.raises(APIError) as exc:
        resolve_location_uri("git+https://github.com/foo/bar.git", str(mount))
    assert exc.value.status_code == 400
    assert exc.value.code == "unsupported_location_scheme"


def test_resolve_empty_uri_400(mount: Path) -> None:
    with pytest.raises(APIError) as exc:
        resolve_location_uri("", str(mount))
    assert exc.value.status_code == 400
    assert exc.value.code == "invalid_location_uri"


def test_resolve_traversal_blocked(mount: Path) -> None:
    """irods:///../etc must not escape the mount."""
    with pytest.raises(APIError) as exc:
        resolve_location_uri("irods:///../etc/passwd", str(mount))
    # Either traversal blocked OR the resolved (clamped) path doesn't exist —
    # both are "we didn't serve the file". The 400 traversal error is preferred.
    assert exc.value.status_code in (400, 404)


def test_resolve_missing_directory_404(mount: Path) -> None:
    with pytest.raises(APIError) as exc:
        resolve_location_uri("irods:///datasets/does-not-exist", str(mount))
    assert exc.value.status_code == 404
    assert exc.value.code == "resource_files_not_found"


# ── safe_join ───────────────────────────────────────────────────


def test_safe_join_returns_file(mount: Path) -> None:
    base = mount / "datasets" / "abc-123"
    assert safe_join(base, "file.csv") == (base / "file.csv").resolve()


def test_safe_join_traversal_blocked(mount: Path) -> None:
    base = mount / "datasets" / "abc-123"
    with pytest.raises(APIError) as exc:
        safe_join(base, "../../etc/passwd")
    assert exc.value.status_code in (400, 404)


def test_safe_join_missing_file_404(mount: Path) -> None:
    base = mount / "datasets" / "abc-123"
    with pytest.raises(APIError) as exc:
        safe_join(base, "does-not-exist.txt")
    assert exc.value.status_code == 404
    assert exc.value.code == "file_not_found"


def test_safe_join_empty_path_400(mount: Path) -> None:
    base = mount / "datasets" / "abc-123"
    with pytest.raises(APIError) as exc:
        safe_join(base, "")
    assert exc.value.status_code == 400


def test_safe_join_directory_rejected(mount: Path) -> None:
    base = mount / "datasets"
    with pytest.raises(APIError) as exc:
        safe_join(base, "abc-123")  # a directory, not a file
    assert exc.value.status_code == 400
    assert exc.value.code == "not_a_file"

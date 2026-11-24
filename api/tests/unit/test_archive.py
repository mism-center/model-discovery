"""Tests for shared archive extraction.

The traversal cases matter most: a member name is attacker-controlled, and
``..`` is not normalized lexically, so containment only holds because each
member is resolved before being compared against the destination root.
"""

from __future__ import annotations

import io
import struct
import tarfile
import zipfile
from pathlib import Path

import pytest

from mismapi.core.archive import extract_tarball, extract_zip
from mismapi.core.errors import APIError

_LIMIT = 10 * 1024 * 1024


def _zip(members: dict[str, bytes]) -> io.BytesIO:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    buf.seek(0)
    return buf


# ── extract_zip: happy path ──────────────────────────────────────────


def test_extracts_flat_members(tmp_path: Path) -> None:
    buf = _zip({"Kirschner_1998.xml": b"<sbml/>", "manifest.xml": b"<omex/>"})

    result = extract_zip(buf, tmp_path, max_total_bytes=_LIMIT)

    assert result.file_count == 2
    assert result.total_bytes == len(b"<sbml/>") + len(b"<omex/>")
    assert (tmp_path / "Kirschner_1998.xml").read_bytes() == b"<sbml/>"
    assert (tmp_path / "manifest.xml").read_bytes() == b"<omex/>"


def test_preserves_nested_directories(tmp_path: Path) -> None:
    buf = _zip({"model/sub/deep.xml": b"x"})

    result = extract_zip(buf, tmp_path, max_total_bytes=_LIMIT)

    assert result.file_count == 1
    assert (tmp_path / "model" / "sub" / "deep.xml").read_bytes() == b"x"


def test_creates_destination_directory(tmp_path: Path) -> None:
    dest = tmp_path / "does" / "not" / "exist"
    extract_zip(_zip({"a.txt": b"a"}), dest, max_total_bytes=_LIMIT)
    assert (dest / "a.txt").exists()


def test_directory_entries_are_not_counted(tmp_path: Path) -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("subdir/", b"")
        zf.writestr("subdir/a.txt", b"a")
    buf.seek(0)

    result = extract_zip(buf, tmp_path, max_total_bytes=_LIMIT)

    assert result.file_count == 1
    assert result.total_bytes == 1


# ── extract_zip: traversal ───────────────────────────────────────────


@pytest.mark.parametrize(
    "name",
    [
        "../escape.txt",
        "../../etc/passwd",
        "a/../../escape.txt",
        "/etc/passwd",
    ],
)
def test_traversal_members_are_skipped(tmp_path: Path, name: str) -> None:
    dest = tmp_path / "dest"
    outside = tmp_path / "escape.txt"

    result = extract_zip(_zip({name: b"pwned"}), dest, max_total_bytes=_LIMIT)

    assert result.file_count == 0
    assert not outside.exists()
    assert not (tmp_path / "etc" / "passwd").exists()
    assert list(dest.rglob("*")) == []


def test_safe_members_still_extract_alongside_traversal(tmp_path: Path) -> None:
    dest = tmp_path / "dest"

    result = extract_zip(
        _zip({"../evil.txt": b"pwned", "good.xml": b"ok"}), dest, max_total_bytes=_LIMIT
    )

    assert result.file_count == 1
    assert (dest / "good.xml").read_bytes() == b"ok"
    assert not (tmp_path / "evil.txt").exists()


# ── extract_zip: size cap ────────────────────────────────────────────


def test_declared_total_over_cap_is_rejected_before_writing(tmp_path: Path) -> None:
    buf = _zip({"big.bin": b"x" * 5000})

    with pytest.raises(APIError) as exc:
        extract_zip(buf, tmp_path, max_total_bytes=100)

    assert exc.value.status_code == 413
    assert exc.value.code == "archive_too_large"
    # Rejected up front — nothing was written.
    assert list(tmp_path.iterdir()) == []


def test_total_exactly_at_cap_is_allowed(tmp_path: Path) -> None:
    result = extract_zip(_zip({"a.bin": b"x" * 100}), tmp_path, max_total_bytes=100)
    assert result.file_count == 1
    assert result.total_bytes == 100


def _understating_zip(payload: bytes) -> io.BytesIO:
    """A zip whose headers claim one byte per member but store `payload`."""
    buf = _zip({"a.bin": payload})
    raw = bytearray(buf.getvalue())
    # Uncompressed size lives at +24 in the central directory record and at
    # +22 in the local file header.
    struct.pack_into("<I", raw, raw.find(b"PK\x01\x02") + 24, 1)
    struct.pack_into("<I", raw, raw.find(b"PK\x03\x04") + 22, 1)
    return io.BytesIO(bytes(raw))


def test_understated_header_cannot_smuggle_bytes_past_the_cap(tmp_path: Path) -> None:
    """zipfile truncates at the declared size and fails the CRC, so a header
    that understates cannot extract more than it declares."""
    with pytest.raises(APIError) as exc:
        extract_zip(_understating_zip(b"x" * 5000), tmp_path, max_total_bytes=100)

    assert exc.value.status_code == 502
    assert exc.value.code == "invalid_archive"
    assert list(tmp_path.iterdir()) == []


# ── extract_zip: corrupt input ───────────────────────────────────────


def test_non_zip_bytes_raise_invalid_archive(tmp_path: Path) -> None:
    with pytest.raises(APIError) as exc:
        extract_zip(
            io.BytesIO(b"<!doctype html><html>nope</html>"), tmp_path, max_total_bytes=_LIMIT
        )

    assert exc.value.status_code == 502
    assert exc.value.code == "invalid_archive"


def test_truncated_zip_raises_invalid_archive(tmp_path: Path) -> None:
    full = _zip({"a.bin": b"x" * 2000}).getvalue()

    with pytest.raises(APIError) as exc:
        extract_zip(io.BytesIO(full[: len(full) // 2]), tmp_path, max_total_bytes=_LIMIT)

    assert exc.value.status_code == 502
    assert exc.value.code == "invalid_archive"


# ── extract_tarball ──────────────────────────────────────────────────


def _tarball(members: dict[str, bytes]) -> io.BytesIO:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    buf.seek(0)
    return buf


def test_tarball_extracts_members_as_named(tmp_path: Path) -> None:
    buf = _tarball({"README.md": b"hi", "src/a.py": b"x"})

    result = extract_tarball(buf, tmp_path, max_total_bytes=_LIMIT)

    assert result.file_count == 2
    assert result.total_bytes == 3
    assert (tmp_path / "README.md").read_bytes() == b"hi"
    assert (tmp_path / "src" / "a.py").read_bytes() == b"x"


def test_tarball_skips_traversal_members(tmp_path: Path) -> None:
    dest = tmp_path / "dest"
    buf = _tarball({"pkg/../../escape.txt": b"pwned"})

    result = extract_tarball(buf, dest, max_total_bytes=_LIMIT)

    assert result.file_count == 0
    assert not (tmp_path / "escape.txt").exists()


def test_tarball_declared_total_over_cap_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(APIError) as exc:
        extract_tarball(_tarball({"big.bin": b"x" * 5000}), tmp_path, max_total_bytes=100)

    assert exc.value.status_code == 413
    assert exc.value.code == "archive_too_large"
    assert list(tmp_path.iterdir()) == []


def test_non_tarball_bytes_raise_invalid_archive(tmp_path: Path) -> None:
    with pytest.raises(APIError) as exc:
        extract_tarball(io.BytesIO(b"not a tarball"), tmp_path, max_total_bytes=_LIMIT)

    assert exc.value.status_code == 502
    assert exc.value.code == "invalid_archive"


# ── strip_root_dir ───────────────────────────────────────────────────


def test_strip_root_dir_flattens_a_single_wrapper(tmp_path: Path) -> None:
    """The shape a GitHub tarball arrives in: one "{owner}-{repo}-{sha}/" root."""
    buf = _tarball({"owner-repo-abc123/README.md": b"hi", "owner-repo-abc123/src/a.py": b"x"})

    result = extract_tarball(buf, tmp_path, max_total_bytes=_LIMIT, strip_root_dir=True)

    assert result.file_count == 2
    assert (tmp_path / "README.md").read_bytes() == b"hi"
    assert (tmp_path / "src" / "a.py").read_bytes() == b"x"
    assert not (tmp_path / "owner-repo-abc123").exists()


def test_strip_root_dir_applies_to_zips_too(tmp_path: Path) -> None:
    buf = _zip({"wrapper/a.xml": b"a", "wrapper/nested/b.xml": b"b"})

    extract_zip(buf, tmp_path, max_total_bytes=_LIMIT, strip_root_dir=True)

    assert (tmp_path / "a.xml").read_bytes() == b"a"
    assert (tmp_path / "nested" / "b.xml").read_bytes() == b"b"


def test_strip_root_dir_is_a_noop_for_root_level_members(tmp_path: Path) -> None:
    """An OMEX archive names its members at the archive root."""
    buf = _zip({"Kirschner_1998.xml": b"<sbml/>", "manifest.xml": b"<omex/>"})

    result = extract_zip(buf, tmp_path, max_total_bytes=_LIMIT, strip_root_dir=True)

    assert result.file_count == 2
    assert (tmp_path / "Kirschner_1998.xml").exists()
    assert (tmp_path / "manifest.xml").exists()


def test_strip_root_dir_is_a_noop_with_several_top_level_entries(tmp_path: Path) -> None:
    buf = _zip({"one/a.xml": b"a", "two/b.xml": b"b"})

    extract_zip(buf, tmp_path, max_total_bytes=_LIMIT, strip_root_dir=True)

    assert (tmp_path / "one" / "a.xml").exists()
    assert (tmp_path / "two" / "b.xml").exists()


def test_strip_root_dir_is_a_noop_when_one_member_sits_at_the_root(tmp_path: Path) -> None:
    """A lone root-level file means there is no wrapper, so nothing is stripped
    and no member is dropped."""
    buf = _zip({"loose.txt": b"x", "wrapper/kept.txt": b"y"})

    result = extract_zip(buf, tmp_path, max_total_bytes=_LIMIT, strip_root_dir=True)

    assert result.file_count == 2
    assert (tmp_path / "loose.txt").exists()
    assert (tmp_path / "wrapper" / "kept.txt").exists()

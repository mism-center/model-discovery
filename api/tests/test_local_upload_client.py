from pathlib import Path

import pytest

from mismapi.clients.local_upload_client import LocalFileUploadClient
from mismapi.core.errors import APIError


@pytest.fixture
def mount(tmp_path: Path) -> Path:
    """Fresh PVC mount root per test."""
    root = tmp_path / "irods"
    root.mkdir()
    return root


# ── Happy path ─────────────────────────────────────────────────


async def test_init_upload_part_complete_writes_file(mount: Path) -> None:
    client = LocalFileUploadClient(mount_path=str(mount))
    try:
        session = await client.init_upload(
            resource_id="ds-1",
            filename="data.bin",
            content_type="application/octet-stream",
        )
        assert session.upload_id.startswith("local-")
        assert session.tracking_id.startswith("track-")

        # During upload: temp file exists, final file does not yet.
        target = mount / "ds-1" / "data.bin"
        temp_dir = mount / "ds-1" / ".uploads"
        assert temp_dir.exists()
        assert not target.exists()

        await client.upload_part(session.upload_id, 1, b"hello ")
        await client.upload_part(session.upload_id, 2, b"world")
        await client.complete_upload(
            upload_id=session.upload_id, total_bytes=11, total_parts=2
        )

        # Final file in place, with the expected bytes.
        assert target.read_bytes() == b"hello world"
        # Temp .part file cleaned up.
        assert list(temp_dir.glob("*.part")) == []
    finally:
        await client.close()


async def test_completed_upload_is_visible_to_download_layout(mount: Path) -> None:
    """The final path is exactly where resolve_location_uri('irods:///ds-1') points."""
    from mismapi.core.file_storage import resolve_location_uri

    client = LocalFileUploadClient(mount_path=str(mount))
    try:
        session = await client.init_upload(
            resource_id="ds-1", filename="readme.txt", content_type="text/plain"
        )
        await client.upload_part(session.upload_id, 1, b"hi")
        await client.complete_upload(session.upload_id, total_bytes=2, total_parts=1)
    finally:
        await client.close()

    # The download endpoint resolves the resource directory like this:
    resolved = resolve_location_uri("irods:///ds-1", str(mount))
    assert (resolved / "readme.txt").read_bytes() == b"hi"


# ── Sanitization ───────────────────────────────────────────────


@pytest.mark.parametrize(
    "bad_resource_id",
    ["", "../etc/passwd", "foo/bar", "a\\b", "..", "ok/../escape"],
)
async def test_init_rejects_unsafe_resource_id(mount: Path, bad_resource_id: str) -> None:
    client = LocalFileUploadClient(mount_path=str(mount))
    try:
        with pytest.raises(APIError) as exc:
            await client.init_upload(
                resource_id=bad_resource_id, filename="x.bin", content_type=None
            )
        assert exc.value.status_code == 400
        assert exc.value.code == "invalid_resource_id"
    finally:
        await client.close()


@pytest.mark.parametrize(
    "bad_filename",
    ["", "../escape.txt", "with space.bin", "weird*name", "/abs/path.bin"],
)
async def test_init_rejects_unsafe_filename(mount: Path, bad_filename: str) -> None:
    client = LocalFileUploadClient(mount_path=str(mount))
    try:
        with pytest.raises(APIError) as exc:
            await client.init_upload(
                resource_id="ds-1", filename=bad_filename, content_type=None
            )
        assert exc.value.status_code == 400
        assert exc.value.code == "invalid_filename"
    finally:
        await client.close()


# ── Failure modes ──────────────────────────────────────────────


async def test_upload_part_unknown_session_returns_404(mount: Path) -> None:
    client = LocalFileUploadClient(mount_path=str(mount))
    try:
        with pytest.raises(APIError) as exc:
            await client.upload_part("does-not-exist", 1, b"data")
        assert exc.value.status_code == 404
        assert exc.value.code == "upload_session_unknown"
    finally:
        await client.close()


async def test_upload_part_out_of_order_400(mount: Path) -> None:
    client = LocalFileUploadClient(mount_path=str(mount))
    try:
        session = await client.init_upload(
            resource_id="ds-1", filename="x.bin", content_type=None
        )
        with pytest.raises(APIError) as exc:
            # Skip part 1 → expect rejection.
            await client.upload_part(session.upload_id, 2, b"data")
        assert exc.value.status_code == 400
        assert exc.value.code == "upload_part_out_of_order"
    finally:
        await client.close()


async def test_complete_size_mismatch_400_and_no_final_file(mount: Path) -> None:
    client = LocalFileUploadClient(mount_path=str(mount))
    try:
        session = await client.init_upload(
            resource_id="ds-1", filename="x.bin", content_type=None
        )
        await client.upload_part(session.upload_id, 1, b"abc")
        with pytest.raises(APIError) as exc:
            # Lie about the size: claim 100 bytes when we wrote 3.
            await client.complete_upload(
                upload_id=session.upload_id, total_bytes=100, total_parts=1
            )
        assert exc.value.status_code == 400
        assert exc.value.code == "upload_size_mismatch"

        # No final file should appear when we lie about the size.
        assert not (mount / "ds-1" / "x.bin").exists()
        # And the temp .part should be cleaned up.
        assert list((mount / "ds-1" / ".uploads").glob("*.part")) == []
    finally:
        await client.close()


# ── close() cleanup ────────────────────────────────────────────


async def test_close_cleans_up_inflight_sessions(mount: Path) -> None:
    client = LocalFileUploadClient(mount_path=str(mount))
    session = await client.init_upload(
        resource_id="ds-1", filename="x.bin", content_type=None
    )
    await client.upload_part(session.upload_id, 1, b"abc")
    # Don't complete — close() should drop the session and remove the temp file.
    await client.close()

    temp_dir = mount / "ds-1" / ".uploads"
    assert list(temp_dir.glob("*.part")) == []
    assert not (mount / "ds-1" / "x.bin").exists()


# ── Stub mode ──────────────────────────────────────────────────


async def test_stub_mode_skips_filesystem(mount: Path) -> None:
    """stub_upstream=True: no files on disk, but the protocol still returns ids."""
    client = LocalFileUploadClient(mount_path=str(mount), stub_upstream=True)
    try:
        session = await client.init_upload(
            resource_id="ds-1", filename="x.bin", content_type=None
        )
        assert session.upload_id.startswith("stub-upload-")

        await client.upload_part(session.upload_id, 1, b"abc")
        await client.complete_upload(session.upload_id, total_bytes=3, total_parts=1)

        # Stub mode does not touch the filesystem.
        assert not (mount / "ds-1").exists()
    finally:
        await client.close()

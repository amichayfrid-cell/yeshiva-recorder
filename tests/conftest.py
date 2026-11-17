import io
import struct
import zipfile
from pathlib import Path
from typing import Optional

import pytest
from fastapi.testclient import TestClient

import config
from web import storage
from web import server


def make_valid_mp3_bytes(frames: int = 20) -> bytes:
    """
    Generates valid MPEG-1 Layer 3 (128kbps, 44.1kHz, Mono/Stereo) frames.
    Frame header 0xFF 0xFB 0x90 0x00 corresponds to 417 bytes per frame.
    Recognized by mutagen.mp3.MP3, EasyID3, and verify_audio_integrity.
    """
    frame = b"\xff\xfb\x90\x00" + (b"\x00" * 413)
    return frame * frames


def make_valid_wav_bytes(
    bext_date: Optional[str] = None,
    bext_time: Optional[str] = None,
    sample_frames: int = 500,
) -> bytes:
    """
    Generates a valid RIFF/WAVE PCM file with optional Broadcast Wave (bext) chunk.
    """
    # fmt chunk: PCM (1), 1 channel, 44100 Hz, 88200 byte/s, block_align 2, 16-bit
    fmt_data = struct.pack("<HHIIHH", 1, 1, 44100, 88200, 2, 16)
    fmt_chunk = b"fmt " + struct.pack("<I", len(fmt_data)) + fmt_data

    bext_chunk = b""
    if bext_date is not None and bext_time is not None:
        bext_buf = bytearray(348)
        d_bytes = bext_date.encode("ascii")[:10]
        t_bytes = bext_time.encode("ascii")[:8]
        bext_buf[320 : 320 + len(d_bytes)] = d_bytes
        bext_buf[330 : 330 + len(t_bytes)] = t_bytes
        bext_chunk = b"bext" + struct.pack("<I", len(bext_buf)) + bytes(bext_buf)

    pcm_data = b"\x01\x00\xff\x7f" * sample_frames
    data_chunk = b"data" + struct.pack("<I", len(pcm_data)) + pcm_data

    body = b"WAVE" + fmt_chunk + bext_chunk + data_chunk
    return b"RIFF" + struct.pack("<I", len(body)) + body


def make_valid_docx(
    path: Path,
    title: str = "כותרת השיעור",
    paragraph: str = "תוכן השיעור בעברית.",
    table_cell: str = "",
) -> Path:
    """Creates a minimal valid DOCX archive containing word/document.xml."""
    path.parent.mkdir(parents=True, exist_ok=True)
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/>'
        "</Relationships>"
    )

    table_xml = ""
    if table_cell:
        table_xml = (
            "<w:tbl><w:tr><w:tc><w:p><w:r><w:t>"
            f"{table_cell}"
            "</w:t></w:r></w:p></w:tc></w:tr></w:tbl>"
        )

    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>"
        '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr>'
        f"<w:r><w:t>{title}</w:t></w:r></w:p>"
        "<w:p><w:r><w:rPr><w:b/><w:i/><w:u w:val=\"single\"/></w:rPr>"
        f"<w:t>{paragraph}</w:t></w:r></w:p>"
        f"{table_xml}"
        "</w:body></w:document>"
    )

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/document.xml", document_xml)

    return path


def _reset_all_caches() -> None:
    """Resets all in-memory caches and session/token registries across modules."""
    config._MOUNT_CACHE = None
    config._MOUNT_CACHE_TIME = 0.0
    config._UPLOAD_DIRS_CACHE = None
    config._UPLOAD_DIRS_CACHE_TIME = 0.0

    storage._RECORDER_SOURCES_CACHE = None
    storage._RECORDER_NEGATIVE_CACHE.clear()
    storage._RECORDER_ALIASES_CACHE = None
    storage._NOTES_CACHE = None
    storage._NOTES_CACHE_MTIME = 0.0
    storage._NOTES_CACHE_TIME = 0.0
    storage.FOLDER_CACHE.clear()
    storage._ALL_FOLDERS_CACHE = None
    storage._ALL_FOLDERS_CACHE_TIME = 0.0
    storage._IS_CRAWLING_FOLDERS = False

    server._PENDING_LESSONS_CACHE = None
    server._PENDING_LESSONS_CACHE_TIME = 0.0
    server._FILE_LOCATION_CACHE.clear()
    server._RAV_TZVI_SOURCES_CACHE = None
    server._RAV_TZVI_CACHE_TIME = 0.0
    server._RAV_TZVI_BROWSE_CACHE.clear()
    server._RAV_TZVI_SEARCH_CACHE.clear()
    server._RAV_TZVI_CATALOG_CACHE = None
    server._RAV_TZVI_CATALOG_TIME = 0.0
    server.ACTIVE_SESSIONS.clear()
    server.STREAMING_TOKENS.clear()


@pytest.fixture(autouse=True)
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    Isolates all filesystem paths and caches to a temporary directory for every test.
    """
    data_dir = tmp_path / "data"
    incoming_dir = data_dir / "incoming"
    staging_dir = data_dir / "needs_review"
    rav_tzvi_dir = data_dir / "rav_tzvi"
    noam_dir = data_dir / "noam"
    local_upload_dir = data_dir / "upload_lessons"
    transcoded_dir = data_dir / "transcoded_cache"
    history_file = data_dir / "history.json"

    net_mount = tmp_path / "mnt_yeshiva_share"
    net_target = net_mount / "שיעורי השבוע"
    net_upload = tmp_path / "mnt_yeshiva_upload"
    net_share_upload = net_mount / "העלאת שיעורים"

    for d in [incoming_dir, staging_dir, rav_tzvi_dir, local_upload_dir, transcoded_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # Patch config paths
    monkeypatch.setattr(config, "DATA_DIR", data_dir)
    monkeypatch.setattr(config, "INCOMING_DIR", incoming_dir)
    monkeypatch.setattr(config, "LOCAL_STAGING_DIR", staging_dir)
    monkeypatch.setattr(config, "RAV_TZVI_DIR", rav_tzvi_dir)
    monkeypatch.setattr(config, "NOAM_DIR", noam_dir)
    monkeypatch.setattr(config, "HISTORY_FILE", history_file)
    monkeypatch.setattr(config, "NETWORK_MOUNT_POINT", net_mount)
    monkeypatch.setattr(config, "NETWORK_TARGET_DIR", net_target)
    monkeypatch.setattr(config, "NETWORK_UPLOAD_MOUNT", net_upload)
    monkeypatch.setattr(config, "NETWORK_SHARE_UPLOAD_SUBDIR", net_share_upload)
    monkeypatch.setattr(config, "LOCAL_UPLOAD_DIR", local_upload_dir)

    # Patch storage paths
    monkeypatch.setattr(storage, "NOTES_FILE", data_dir / "notes.json")
    monkeypatch.setattr(storage, "RECORDER_SOURCES_FILE", data_dir / "recorder_sources.json")
    monkeypatch.setattr(storage, "RECORDER_ALIASES_FILE", data_dir / "recorder_aliases.json")
    monkeypatch.setattr(storage, "FOLDERS_CACHE_FILE", data_dir / "folders_tree_cache.json")

    # Patch server paths
    monkeypatch.setattr(server, "TRANSCODED_CACHE_DIR", transcoded_dir)

    _reset_all_caches()
    yield tmp_path
    _reset_all_caches()


@pytest.fixture
def client() -> TestClient:
    """Unauthenticated FastAPI TestClient."""
    return TestClient(server.app)


@pytest.fixture
def auth_client() -> TestClient:
    """Authenticated FastAPI TestClient with a valid admin session cookie."""
    token = "test-admin-session-token"
    server.ACTIVE_SESSIONS.add(token)
    c = TestClient(server.app)
    c.cookies.set(server.COOKIE_NAME, token)
    return c

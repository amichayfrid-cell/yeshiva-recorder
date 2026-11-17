import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from mutagen.mp3 import MP3

import config
from core import usb_ingest
from tests.conftest import make_valid_mp3_bytes, make_valid_wav_bytes
from web import storage


def test_decode_hebrew_filename_cp862_and_cp1255():
    hebrew_name = "שיעור_כללי.mp3"
    garbled_cp862 = hebrew_name.encode("cp862").decode("latin1")
    garbled_cp1255 = hebrew_name.encode("cp1255").decode("latin1")

    assert usb_ingest.decode_hebrew_filename(garbled_cp862) == hebrew_name
    assert usb_ingest.decode_hebrew_filename(garbled_cp1255) == hebrew_name
    assert usb_ingest.decode_hebrew_filename(hebrew_name) == hebrew_name
    assert usb_ingest.decode_hebrew_filename("english_file.mp3") == "english_file.mp3"


def test_verify_audio_integrity(tmp_path: Path):
    mp3_file = tmp_path / "valid.mp3"
    mp3_bytes = make_valid_mp3_bytes()
    mp3_file.write_bytes(mp3_bytes)
    assert usb_ingest.verify_audio_integrity(mp3_file, len(mp3_bytes)) is True
    assert usb_ingest.verify_audio_integrity(mp3_file, len(mp3_bytes) + 1) is False

    wav_file = tmp_path / "valid.wav"
    wav_bytes = make_valid_wav_bytes()
    wav_file.write_bytes(wav_bytes)
    assert usb_ingest.verify_audio_integrity(wav_file, len(wav_bytes)) is True

    empty_file = tmp_path / "empty.mp3"
    empty_file.write_bytes(b"")
    assert usb_ingest.verify_audio_integrity(empty_file, 0) is False

    corrupt_mp3 = tmp_path / "corrupt.mp3"
    corrupt_data = b"NOT_AN_MP3_HEADER_DATA_123456"
    corrupt_mp3.write_bytes(corrupt_data)
    assert usb_ingest.verify_audio_integrity(corrupt_mp3, len(corrupt_data)) is False

    corrupt_wav = tmp_path / "corrupt.wav"
    corrupt_wav.write_bytes(b"NOT_RIFF_DATA")
    assert usb_ingest.verify_audio_integrity(corrupt_wav, 13) is False

    assert usb_ingest.verify_audio_integrity(tmp_path / "missing.mp3", 10) is False


def test_get_drive_label_strategies(tmp_path: Path, monkeypatch):
    # 1. Root identification filename (.txt)
    d1 = tmp_path / "drive1"
    d1.mkdir()
    (d1 / "מקלט 4.txt").write_text("", encoding="utf-8")
    assert usb_ingest.get_drive_label(d1) == "מקלט 4"

    # 2. Content inside recorder.txt
    d2 = tmp_path / "drive2"
    d2.mkdir()
    (d2 / "recorder.txt").write_text("RECORDER_7\nextra line", encoding="utf-8")
    assert usb_ingest.get_drive_label(d2) == "מקלט 7"

    # 2b. Identifier .ini filename
    d2b = tmp_path / "drive2b"
    d2b.mkdir()
    (d2b / "RECORDER_8.ini").write_text("", encoding="utf-8")
    assert usb_ingest.get_drive_label(d2b) == "מקלט 8"

    # 3. Directory / mount point name
    d3 = tmp_path / "MIKLET 3"
    d3.mkdir()
    assert usb_ingest.get_drive_label(d3) == "מקלט 3"

    # 4. Linux sd[b-z] partition fallback (e.g. usb_sdd1 -> sdd -> 3)
    monkeypatch.setattr(usb_ingest.sys, "platform", "linux")
    assert usb_ingest.get_drive_label(Path("/media/usb_sdd1")) == "מקלט 3"


def test_copy_and_verify_from_usb_success_and_wipe(tmp_path: Path):
    src_dir = tmp_path / "usb"
    src_dir.mkdir()
    src_file = src_dir / "20261114_113000.mp3"
    src_file.write_bytes(make_valid_mp3_bytes())

    dest = usb_ingest.copy_and_verify_from_usb(
        src_file,
        target_dir=config.INCOMING_DIR,
        delete_source=True,
        recorder_name="מקלט 2",
    )

    assert dest is not None
    assert dest.exists()
    assert dest.parent == config.INCOMING_DIR
    assert not src_file.exists()
    assert storage.get_recorder_source(dest.name) == "מקלט 2"

    raw = MP3(str(dest))
    assert [str(f.text[0]) for f in raw.tags.getall("TXXX") if f.desc == "recorder"] == ["מקלט 2"]


def test_copy_and_verify_from_usb_keeps_source_and_handles_duplicate_and_errors(tmp_path: Path):
    src_dir = tmp_path / "usb"
    src_dir.mkdir()

    # Keep source when delete_source=False
    src1 = src_dir / "keep_me.mp3"
    data1 = make_valid_mp3_bytes()
    src1.write_bytes(data1)
    dest1 = usb_ingest.copy_and_verify_from_usb(src1, target_dir=config.INCOMING_DIR, delete_source=False)
    assert dest1 is not None and dest1.exists()
    assert src1.exists()

    # Duplicate of exact same size skips copy and wipes source if delete_source=True
    dest_dup = usb_ingest.copy_and_verify_from_usb(src1, target_dir=config.INCOMING_DIR, delete_source=True)
    assert dest_dup == dest1
    assert not src1.exists()

    # Empty 0-byte file is skipped
    empty_src = src_dir / "empty.mp3"
    empty_src.write_bytes(b"")
    assert usb_ingest.copy_and_verify_from_usb(empty_src, target_dir=config.INCOMING_DIR, delete_source=True) is None

    # Corrupt MP3 fails integrity check, rolls back .part_ file, and leaves source intact
    bad_src = src_dir / "corrupt.mp3"
    bad_src.write_bytes(b"GARBAGE_NOT_MP3_BYTES_AT_ALL")
    assert usb_ingest.copy_and_verify_from_usb(bad_src, target_dir=config.INCOMING_DIR, delete_source=True) is None
    assert bad_src.exists()
    assert not list(config.INCOMING_DIR.glob(".part_*"))


def test_scan_and_ingest_path_recursive(tmp_path: Path):
    usb_root = tmp_path / "usb_drive"
    sub = usb_root / "FOLDER01"
    sub.mkdir(parents=True)

    (usb_root / "מקלט 5.txt").write_text("", encoding="utf-8")
    (usb_root / ".hidden.mp3").write_bytes(make_valid_mp3_bytes())
    (usb_root / "notes.txt").write_text("ignore me", encoding="utf-8")
    mp3_a = sub / "REC_01.mp3"
    wav_b = sub / "REC_02.wav"
    mp3_a.write_bytes(make_valid_mp3_bytes())
    wav_b.write_bytes(make_valid_wav_bytes())

    ingested = usb_ingest.scan_and_ingest_path(
        usb_root,
        target_dir=config.INCOMING_DIR,
        delete_source=True,
    )

    names = {p.name for p in ingested}
    assert names == {"REC_01.mp3", "REC_02.wav"}
    assert not mp3_a.exists()
    assert not wav_b.exists()
    assert storage.get_recorder_source("REC_01.mp3") == "מקלט 5"
    assert storage.get_recorder_source("REC_02.wav") == "מקלט 5"


def test_get_removable_mounts_windows_and_linux(monkeypatch):
    fake_psutil_win = SimpleNamespace(
        disk_partitions=lambda all=False: [
            SimpleNamespace(mountpoint="C:\\", opts="rw,fixed", fstype="NTFS"),
            SimpleNamespace(mountpoint="D:\\", opts="rw,removable", fstype="FAT32"),
            SimpleNamespace(mountpoint="E:\\", opts="ro,cdrom", fstype="CDFS"),
            SimpleNamespace(mountpoint="F:\\", opts="rw", fstype="exFAT"),
        ]
    )
    monkeypatch.setattr(usb_ingest, "psutil", fake_psutil_win)
    monkeypatch.setattr(usb_ingest.sys, "platform", "win32")

    win_mounts = usb_ingest.get_removable_mounts()
    assert win_mounts == [Path("D:\\"), Path("F:\\")]

    fake_psutil_linux = SimpleNamespace(
        disk_partitions=lambda all=False: [
            SimpleNamespace(mountpoint="/", opts="rw", fstype="ext4"),
            SimpleNamespace(mountpoint="/media/usb_sdb1", opts="rw", fstype="vfat"),
            SimpleNamespace(mountpoint=str(config.NETWORK_MOUNT_POINT), opts="rw", fstype="cifs"),
            SimpleNamespace(mountpoint="/mnt/other_smb", opts="rw", fstype="smb3"),
            SimpleNamespace(mountpoint="/mnt/sd_card", opts="rw,removable", fstype="exfat"),
        ]
    )
    monkeypatch.setattr(usb_ingest, "psutil", fake_psutil_linux)
    monkeypatch.setattr(usb_ingest.sys, "platform", "linux")
    monkeypatch.setattr(usb_ingest, "auto_mount_linux_usb", lambda: None)

    linux_mounts = usb_ingest.get_removable_mounts()
    assert Path("/media/usb_sdb1") in linux_mounts
    assert Path("/mnt/sd_card") in linux_mounts
    assert config.NETWORK_MOUNT_POINT not in linux_mounts
    assert Path("/mnt/other_smb") not in linux_mounts

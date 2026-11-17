import hashlib
import json
import os
import time
from pathlib import Path

import pytest
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3

import config
from core import file_manager
from tests.conftest import make_valid_mp3_bytes


def test_calculate_sha256(tmp_path: Path):
    f = tmp_path / "sample.bin"
    payload = b"yeshiva-recorder-sha256-payload" * 200
    f.write_bytes(payload)

    expected = hashlib.sha256(payload).hexdigest()
    assert file_manager.calculate_sha256(str(f)) == expected


def test_get_unique_filepath(tmp_path: Path):
    base = "lesson.mp3"
    p0 = file_manager.get_unique_filepath(tmp_path, base)
    assert p0 == tmp_path / "lesson.mp3"

    p0.write_bytes(b"a")
    p1 = file_manager.get_unique_filepath(tmp_path, base)
    assert p1 == tmp_path / "lesson_1.mp3"

    p1.write_bytes(b"b")
    p2 = file_manager.get_unique_filepath(tmp_path, base)
    assert p2 == tmp_path / "lesson_2.mp3"


def test_safe_move_atomic_and_missing_source(tmp_path: Path):
    missing = tmp_path / "does_not_exist.mp3"
    with pytest.raises(FileNotFoundError):
        file_manager.safe_move(str(missing), tmp_path / "dest.mp3")

    src = tmp_path / "src.mp3"
    src.write_bytes(b"atomic-audio-bytes")
    dest = tmp_path / "nested" / "dest.mp3"

    res = file_manager.safe_move(str(src), dest)
    assert res == dest
    assert dest.read_bytes() == b"atomic-audio-bytes"
    assert not src.exists()


def test_safe_move_cross_filesystem_fallback_and_cleanup(tmp_path: Path, monkeypatch):
    src = tmp_path / "src_cross.mp3"
    src.write_bytes(b"cross-fs-audio-data")
    dest = tmp_path / "target" / "dest_cross.mp3"

    real_replace = os.replace

    def fail_replace(s, d):
        if Path(s) in (src, tmp_path / "src_bad.mp3"):
            raise OSError("EXDEV cross-device link")
        return real_replace(s, d)

    monkeypatch.setattr(os, "replace", fail_replace)

    res = file_manager.safe_move(str(src), dest)
    assert res == dest
    assert dest.read_bytes() == b"cross-fs-audio-data"
    assert not src.exists()
    assert not (dest.parent / f".tmp_{dest.name}").exists()

    # Now simulate corrupt partial copy (size mismatch) -> raises IOError & removes temp
    src2 = tmp_path / "src_bad.mp3"
    src2.write_bytes(b"full-length-bytes")
    dest2 = tmp_path / "target" / "dest_bad.mp3"

    def short_copy(s, d):
        Path(d).write_bytes(b"short")

    monkeypatch.setattr(file_manager.shutil, "copy2", short_copy)

    with pytest.raises(IOError, match="size mismatch"):
        file_manager.safe_move(str(src2), dest2)

    assert src2.exists()
    assert not dest2.exists()
    assert not (dest2.parent / f".tmp_{dest2.name}").exists()


def test_apply_id3_tags_writes_tags_and_preserves_mtime(tmp_path: Path):
    wav = tmp_path / "audio.wav"
    wav.write_bytes(b"RIFF....WAVE")
    assert file_manager.apply_id3_tags(wav, {"rabbi": "הרב צבי"}) is False

    mp3_file = tmp_path / "lesson.mp3"
    mp3_file.write_bytes(make_valid_mp3_bytes())
    fixed_ts = 1700000000.0
    os.utime(str(mp3_file), (fixed_ts, fixed_ts))

    ok = file_manager.apply_id3_tags(
        mp3_file,
        metadata={"rabbi": "הרב דוד", "topic": "פרשת השבוע", "recorder": "מקלט 2"},
        hebrew_date_str="ה_כסלו_תשפז",
    )
    assert ok is True

    tags = EasyID3(str(mp3_file))
    assert tags["artist"] == ["הרב דוד"]
    assert tags["title"] == ["פרשת השבוע"]
    assert tags["album"] == ["שיעורי תורה - ה כסלו תשפז"]

    raw = MP3(str(mp3_file))
    txxx_vals = [str(f.text[0]) for f in raw.tags.getall("TXXX") if f.desc == "recorder"]
    assert txxx_vals == ["מקלט 2"]

    assert abs(mp3_file.stat().st_mtime - fixed_ts) < 2.0


def test_cleanup_temp_files_deletes_only_old_files(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(config, "BASE_DIR", tmp_path)
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path / "sys_tmp"))
    (tmp_path / "sys_tmp").mkdir()

    old_mp3 = tmp_path / "tmp_old.mp3"
    fresh_mp3 = tmp_path / "tmp_fresh.mp3"
    old_wav = tmp_path / "sys_tmp" / "tmp_old.wav"
    keep_other = tmp_path / "normal.mp3"

    for p in (old_mp3, fresh_mp3, old_wav, keep_other):
        p.write_bytes(b"temp")

    old_time = time.time() - 400
    os.utime(str(old_mp3), (old_time, old_time))
    os.utime(str(old_wav), (old_time, old_time))

    deleted = file_manager.cleanup_temp_files()
    assert deleted == 2
    assert not old_mp3.exists()
    assert not old_wav.exists()
    assert fresh_mp3.exists()
    assert keep_other.exists()


def test_record_history_rotation_and_csv(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(config, "MAX_HISTORY_ENTRIES", 3)

    for i in range(5):
        target = config.LOCAL_STAGING_DIR / f"file_{i}.mp3"
        target.write_bytes(make_valid_mp3_bytes())
        file_manager.record_history(
            original_filename=f"orig_{i}.mp3",
            final_filepath=target,
            status="sorted" if i % 2 == 0 else "needs_review",
            metadata={"rabbi": f"הרב {i}", "topic": f"נושא {i}"},
        )

    history = json.loads(config.HISTORY_FILE.read_text(encoding="utf-8"))
    assert len(history) == 3
    assert [e["original_filename"] for e in history] == ["orig_2.mp3", "orig_3.mp3", "orig_4.mp3"]
    assert history[-1]["sha256"] == file_manager.calculate_sha256(str(config.LOCAL_STAGING_DIR / "file_4.mp3"))

    csv_path = config.DATA_DIR / "processing_report.csv"
    assert csv_path.exists()
    csv_text = csv_path.read_text(encoding="utf-8-sig")
    lines = csv_text.strip().splitlines()
    assert len(lines) == 6  # header + 5 entries
    assert "זמן עיבוד" in lines[0]
    assert "סווג בהצלחה" in lines[1]
    assert "לבדיקה ידנית" in lines[2]

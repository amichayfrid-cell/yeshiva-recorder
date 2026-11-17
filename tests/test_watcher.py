import json
import os
import time
from datetime import datetime
from pathlib import Path

from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3

import config
import reset_data
from core import hebrew_date, watcher
from tests.conftest import make_valid_mp3_bytes
from web import storage


def test_is_file_ready_checks_hidden_part_empty_and_stable(tmp_path: Path):
    part_file = tmp_path / "rec.mp3.part"
    part_file.write_bytes(make_valid_mp3_bytes())
    assert watcher.is_file_ready(part_file, wait_seconds=0.01) is False

    hidden_file = tmp_path / ".hidden.mp3"
    hidden_file.write_bytes(make_valid_mp3_bytes())
    assert watcher.is_file_ready(hidden_file, wait_seconds=0.01) is False

    empty_file = tmp_path / "empty.mp3"
    empty_file.write_bytes(b"")
    assert watcher.is_file_ready(empty_file, wait_seconds=0.01) is False

    ready_file = tmp_path / "ready.mp3"
    ready_file.write_bytes(make_valid_mp3_bytes())
    assert watcher.is_file_ready(ready_file, wait_seconds=0.01) is True


def test_generate_timestamp_filename():
    dt = datetime(2026, 11, 14, 19, 30, 0)
    heb = hebrew_date.get_hebrew_date_str(dt, check_sunset=False)
    generated = watcher.generate_timestamp_filename(dt, original_extension=".mp3")
    assert generated == f"({heb}) 19.30.mp3"


def test_process_single_audio_file_pipeline():
    src = config.INCOMING_DIR / "20261114_193000.mp3"
    src.write_bytes(make_valid_mp3_bytes())
    storage.set_recorder_source(src.name, "מקלט 3")

    final_path = watcher.process_single_audio_file(src)

    expected_dt = datetime(2026, 11, 14, 19, 30, 0)
    expected_heb = hebrew_date.get_hebrew_date_str(expected_dt, check_sunset=False)

    assert not src.exists()
    assert final_path.exists()
    assert final_path.parent == config.LOCAL_STAGING_DIR
    assert final_path.name == f"({expected_heb}) 19.30.mp3"
    assert storage.get_recorder_source(final_path.name) == "מקלט 3"
    assert abs(final_path.stat().st_mtime - expected_dt.timestamp()) < 2.0

    easy = EasyID3(str(final_path))
    assert easy["album"] == [f"שיעורי תורה - {expected_heb}"]

    raw = MP3(str(final_path))
    assert [str(f.text[0]) for f in raw.tags.getall("TXXX") if f.desc == "recorder"] == ["מקלט 3"]

    history = json.loads(config.HISTORY_FILE.read_text(encoding="utf-8"))
    assert len(history) == 1
    assert history[0]["original_filename"] == "20261114_193000.mp3"
    assert history[0]["status"] == "in_local_staging"


def test_sync_local_staging_to_network():
    config.NETWORK_TARGET_DIR.mkdir(parents=True, exist_ok=True)
    staged = config.LOCAL_STAGING_DIR / "(ד כסלו תשפז) 10.00.mp3"
    staged.write_bytes(make_valid_mp3_bytes())

    watcher.sync_local_staging_to_network()

    assert not staged.exists()
    assert (config.NETWORK_TARGET_DIR / staged.name).exists()


def test_cleanup_incomplete_transfers():
    stale_part1 = config.INCOMING_DIR / ".part_1234.mp3"
    stale_part2 = config.LOCAL_STAGING_DIR / "recording.mp3.part"
    fresh_part = config.INCOMING_DIR / ".part_fresh.mp3"

    for p in (stale_part1, stale_part2, fresh_part):
        p.write_bytes(b"partial")

    old_ts = time.time() - 60
    os.utime(str(stale_part1), (old_ts, old_ts))
    os.utime(str(stale_part2), (old_ts, old_ts))

    cleaned = watcher.cleanup_incomplete_transfers()
    assert cleaned == 2
    assert not stale_part1.exists()
    assert not stale_part2.exists()
    assert fresh_part.exists()


def test_process_inbox_processes_only_ready_audio(monkeypatch):
    audio1 = config.INCOMING_DIR / "20261115_081500.mp3"
    audio1.write_bytes(make_valid_mp3_bytes())
    ignored_part = config.INCOMING_DIR / "copying.mp3.part"
    ignored_part.write_bytes(make_valid_mp3_bytes())
    ignored_txt = config.INCOMING_DIR / "readme.txt"
    ignored_txt.write_text("hello", encoding="utf-8")

    monkeypatch.setattr(watcher, "is_file_ready", lambda fp, wait_seconds=0.01: True)

    processed = watcher.process_inbox()
    assert len(processed) == 1
    assert processed[0].exists()
    assert not audio1.exists()
    assert ignored_part.exists()
    assert ignored_txt.exists()


def test_reset_data_restores_original_names_and_clears_history():
    src = config.INCOMING_DIR / "REC_ORIG_42.mp3"
    src.write_bytes(make_valid_mp3_bytes())
    final_path = watcher.process_single_audio_file(src)

    name_map = reset_data.get_original_name_map()
    assert name_map.get(final_path.name) == "REC_ORIG_42.mp3"

    reset_data.reset_files(restore_original_names=True, clear_history=True)

    assert not final_path.exists()
    assert (config.INCOMING_DIR / "REC_ORIG_42.mp3").exists()
    assert not config.HISTORY_FILE.exists()

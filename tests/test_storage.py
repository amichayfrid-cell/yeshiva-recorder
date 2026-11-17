import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from mutagen.id3 import TXXX
from mutagen.mp3 import MP3

import config
from tests.conftest import make_valid_mp3_bytes
from web import storage


def test_decode_raw_label_hex_octal_and_latin1():
    # CP862 bytes for "מקלט" are \x8e\x97\x8c\x88
    assert storage.decode_raw_label(r"\x8e\x97\x8c\x88 4") == "מקלט 4"
    # Octal multi-byte and single-byte escapes: 0x8e=216, 0x97=227, 0x8c=214, 0x88=210 -> CP862 'מקלט'
    assert storage.decode_raw_label(r"\216\227\214\210 4") == "מקלט 4"
    assert storage.decode_raw_label(r"\216 4") == "מ 4"
    # Latin1-misread CP1255 bytes for "מקלט"
    latin1_misread = "מקלט 2".encode("cp1255").decode("latin1")
    assert storage.decode_raw_label(latin1_misread) == "מקלט 2"
    assert storage.decode_raw_label(None) == ""


def test_normalize_recorder_label_variants_and_aliases():
    assert storage.normalize_recorder_label(r"\x8e\x97\x8c\x88 4") == "מקלט 4"
    assert storage.normalize_recorder_label("RECORDER_4") == "מקלט 4"
    assert storage.normalize_recorder_label("REC-4") == "מקלט 4"
    assert storage.normalize_recorder_label("MIKLET 4") == "מקלט 4"
    assert storage.normalize_recorder_label("04") == "מקלט 4"
    assert storage.normalize_recorder_label("בית מדרש") == "מקלט בית מדרש"
    assert storage.normalize_recorder_label("מקלט בית מדרש") == "מקלט בית מדרש"
    assert storage.normalize_recorder_label("מקלט ראשי") == "מקלט ראשי"
    assert storage.normalize_recorder_label("recorder") is None

    # Generic / drive-letter artifacts should return None
    assert storage.normalize_recorder_label("SANDISK") is None
    assert storage.normalize_recorder_label("NO NAME") is None
    assert storage.normalize_recorder_label("D") is None
    assert storage.normalize_recorder_label("מקלט O") is None

    # Saved aliases override normalization
    storage.save_recorder_alias("old_dev", "בית מדרש עליון")
    assert storage.normalize_recorder_label("old_dev") == "בית מדרש עליון"
    assert storage.get_recorder_aliases()["old_dev"] == "בית מדרש עליון"


def test_recorder_sources_crud_and_fallbacks():
    storage.set_recorder_source("folder/lesson.mp3", "RECORDER_3")
    assert storage.get_recorder_source("lesson.mp3") == "מקלט 3"
    # Collision suffix fallback (_1.mp3)
    assert storage.get_recorder_source("lesson_1.mp3") == "מקלט 3"

    # ID3 TXXX:recorder fallback when not in JSON
    id3_mp3 = config.LOCAL_STAGING_DIR / "from_id3.mp3"
    id3_mp3.write_bytes(make_valid_mp3_bytes())
    raw = MP3(str(id3_mp3))
    raw.add_tags()
    raw.tags.add(TXXX(encoding=3, desc="recorder", text=["MIKLET 6"]))
    raw.save()
    assert storage.get_recorder_source("from_id3.mp3", filepath=id3_mp3) == "מקלט 6"

    # Pending audio file in sorting dir gets mapped by set_all_recorders_source
    pending_mp3 = config.LOCAL_STAGING_DIR / "pending_a.mp3"
    pending_mp3.write_bytes(make_valid_mp3_bytes())
    storage.set_recorder_source("other.mp3", "מקלט 3")
    storage.set_all_recorders_source("מקלט 3", "בית מדרש")
    assert storage.get_recorder_source("lesson.mp3") == "מקלט בית מדרש"
    assert storage.get_recorder_source("other.mp3") == "מקלט בית מדרש"
    assert storage.get_recorder_source("pending_a.mp3") == "מקלט בית מדרש"

    storage.remove_recorder_source("lesson.mp3")
    assert storage.get_recorder_source("lesson.mp3") is None


def test_notes_crud_and_30_day_pruning():
    n1 = storage.save_note(
        filename="path/to/lesson_a.mp3",
        original_path="Z:\\lessons\\lesson_a.mp3",
        note_type="הערה",
        description="חסר סוף השיעור",
        student_name="יוסי",
    )
    assert n1["filename"] == "lesson_a.mp3"
    assert n1["status"] == "open"
    assert len(storage.get_notes_for_file("lesson_a.mp3")) == 1

    # Update via int ID and string ID
    assert storage.update_note_status(n1["id"], "resolved") is True
    assert storage.get_notes_for_file("lesson_a.mp3") == []
    assert storage.update_note_status(str(n1["id"]), "open") is True
    assert len(storage.get_notes_for_file("lesson_a.mp3")) == 1

    # Old note (>= 30 days) auto-pruned on load
    old_dt = (datetime.now() - timedelta(days=35)).strftime("%Y-%m-%d %H:%M:%S")
    recent_dt = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
    notes_payload = [
        {"id": 1001, "filename": "old.mp3", "created_at": old_dt, "status": "open"},
        {"id": 1002, "filename": "recent.mp3", "created_at": recent_dt, "status": "open"},
    ]
    storage.NOTES_FILE.write_text(json.dumps(notes_payload, ensure_ascii=False), encoding="utf-8")
    storage.invalidate_notes_cache()

    loaded = storage.get_notes_data()
    assert [n["id"] for n in loaded] == [1002]
    assert loaded[0]["hebrew_date"]
    assert loaded[0]["created_time"] == recent_dt.split()[1][:5]


def test_ignored_folders_and_directory_browsing_and_search():
    assert storage.is_ignored_folder_name(".git") is True
    assert storage.is_ignored_folder_name("שיעורים למיון") is True
    assert storage.is_ignored_folder_name("ארכיון שיעורים") is True
    assert storage.is_ignored_folder_name("על הגברת החירות") is True
    assert storage.is_ignored_folder_name("אחראי שמע") is True
    assert storage.is_ignored_folder_name("הרב צבי") is False
    assert storage.is_ignored_folder_path("אלול/ארכיון/הרב") is True
    assert storage.is_ignored_folder_path("אלול/רבני הישיבה") is False

    # Build folder tree under NETWORK_MOUNT_POINT
    root = config.NETWORK_MOUNT_POINT
    (root / "שנת התשפז" / "רבני הישיבה" / "הרב אורי" / "עיון בבא מציעא").mkdir(parents=True)
    (root / "שנת התשפז" / "ארכיון ישן").mkdir(parents=True)
    (root / "שיעורים למיון").mkdir(parents=True)
    (root / "שנת התשפז" / "sample.mp3").write_bytes(make_valid_mp3_bytes())

    listing = storage.list_direct_subfolders()
    assert listing["is_root"] is True
    assert [f["name"] for f in listing["subfolders"]] == ["שנת התשפז"]

    sub_listing = storage.list_direct_subfolders("שנת התשפז")
    assert sub_listing["is_root"] is False
    assert [f["name"] for f in sub_listing["subfolders"]] == ["רבני הישיבה"]
    assert sub_listing["audio_files"] == ["sample.mp3"]

    flat = storage.get_all_folders_flat()
    flat_names = {f["name"] for f in flat}
    assert "הרב אורי" in flat_names
    assert "עיון בבא מציעא" in flat_names
    assert "ארכיון ישן" not in flat_names
    assert "שיעורים למיון" not in flat_names

    # Multi-word search across breadcrumb path
    res = storage.search_folders("הרב אורי")
    assert any(r["name"] == "הרב אורי" for r in res)
    res_deep = storage.search_folders("אורי בבא מציעא")
    assert len(res_deep) == 1
    assert res_deep[0]["name"] == "עיון בבא מציעא"

    # Create new folder & validation
    created = storage.create_new_folder(str(root / "שנת התשפז"), "שיעור כללי")
    assert Path(created).is_dir()
    with pytest.raises(ValueError):
        storage.create_new_folder(str(root), "   ")

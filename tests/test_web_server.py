import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from mutagen.easyid3 import EasyID3

import config
from core import hebrew_date
from tests.conftest import make_valid_docx, make_valid_mp3_bytes
from web import server, storage


# ==========================================
# Hebrew Fuzzy Matching & Path Resolution
# ==========================================

def test_hebrew_normalization_and_fuzzy_matching():
    assert server.normalize_hebrew_string("ר\u05f3 אליאב התשפ\u05f4ז") == 'ר\' אליאב התשפ"ז'
    assert server.normalize_hebrew_string("שנת התשפ''ז") == 'שנת התשפ"ז'

    k1 = server.hebrew_compare_key("ר' אליאב שניצר (כא אלול פו).mp3")
    k2 = server.hebrew_compare_key("ר אליאב שניצר (כא אלול פו).mp3")
    assert k1 == k2

    assert server.hebrew_keys_match("49הרב דרור (י כסלו).mp3", "הרב דרור (י כסלו).mp3") is True
    assert server.hebrew_keys_match("01הרב דרור.mp3", "1הרב דרור.mp3") is True
    assert server.hebrew_keys_match("01הרב דרור.mp3", "02הרב דרור.mp3") is False
    assert server.hebrew_keys_match("", "הרב דרור") is False


def test_resolve_path_with_fuzzy_hebrew_and_unc_paths(tmp_path: Path):
    base = config.NETWORK_MOUNT_POINT
    target_dir = base / "שנת התשפ״ז" / "רבני הישיבה" / "ר' אליאב"
    target_dir.mkdir(parents=True)
    lesson = target_dir / "שיעור_א' (כא אלול).mp3"
    lesson.write_bytes(make_valid_mp3_bytes())

    # Fuzzy match replacing Hebrew gershayim/geresh with ASCII quotes
    resolved = server.resolve_path_with_fuzzy_hebrew(
        base, ['שנת התשפ"ז', "רבני הישיבה", "ר׳ אליאב", "שיעור א (כא אלול).mp3"]
    )
    assert resolved == lesson

    # Windows SMB UNC path resolution
    unc = r"\\mdserver\שיעורי שמע\שנת התשפ''ז\רבני הישיבה\ר אליאב\שיעור א (כא אלול).mp3"
    candidates = server.resolve_possible_local_paths(unc)
    assert lesson in candidates

    # Drive letter path resolution
    drive_path = r"Z:\שנת התשפ''ז\רבני הישיבה\ר אליאב\שיעור א (כא אלול).mp3"
    assert lesson in server.resolve_possible_local_paths(drive_path)

    # locate_lesson_file resolves via original_path
    found = server.locate_lesson_file("שיעור א (כא אלול).mp3", original_path=unc)
    assert found == lesson


# ==========================================
# Auth & Session Routes
# ==========================================

def test_auth_and_session_lifecycle(client):
    res_root = client.get("/", follow_redirects=False)
    assert res_root.status_code in (302, 307)
    assert res_root.headers["location"] == "/admin"

    res_admin_unauth = client.get("/admin", follow_redirects=False)
    assert res_admin_unauth.status_code in (302, 307)
    assert res_admin_unauth.headers["location"] == "/login"

    res_api_unauth = client.get("/api/lessons/pending")
    assert res_api_unauth.status_code == 401

    res_bad_login = client.post("/login", data={"password": "wrong-password"}, follow_redirects=False)
    assert res_bad_login.status_code == 302
    assert res_bad_login.headers["location"] == "/login?error=1"

    res_good_login = client.post("/login", data={"password": server.ADMIN_PASSWORD}, follow_redirects=False)
    assert res_good_login.status_code == 302
    assert res_good_login.headers["location"] == "/admin"
    assert server.COOKIE_NAME in res_good_login.cookies
    assert len(server.ACTIVE_SESSIONS) == 1

    res_admin_auth = client.get("/admin")
    assert res_admin_auth.status_code == 200
    assert "text/html" in res_admin_auth.headers["content-type"]

    res_logout = client.get("/logout", follow_redirects=False)
    assert res_logout.status_code == 302
    assert res_logout.headers["location"] == "/login"
    assert len(server.ACTIVE_SESSIONS) == 0


# ==========================================
# Student Portal & Notes APIs
# ==========================================

def test_student_portal_and_notes_api(client, auth_client):
    res_page = client.get("/student", params={"file": r"Z:\שיעורים\lesson_check.mp3"})
    assert res_page.status_code == 200
    assert "lesson_check.mp3" in res_page.text

    res_post = client.post(
        "/api/student/notes",
        data={
            "filename": "lesson_check.mp3",
            "original_path": r"Z:\שיעורים\lesson_check.mp3",
            "description": "הקלטה חלשה בדקה 10",
            "student_name": "דוד",
        },
    )
    assert res_post.status_code == 200
    note = res_post.json()["note"]
    assert note["filename"] == "lesson_check.mp3"
    assert note["status"] == "open"

    res_all = auth_client.get("/api/notes/all")
    assert res_all.status_code == 200
    assert len(res_all.json()["notes"]) == 1

    res_status = auth_client.post("/api/notes/status", data={"note_id": note["id"], "status": "resolved"})
    assert res_status.status_code == 200
    assert res_status.json()["status"] == "success"
    assert storage.get_notes_for_file("lesson_check.mp3") == []


# ==========================================
# Pending Lessons, Classification, Update & Delete
# ==========================================

def test_pending_lessons_auto_fixes_hebrew_date_and_attaches_notes_and_labels(auth_client):
    # Create a recorder file with an outdated Hebrew date prefix
    dt = datetime(2026, 11, 14, 12, 0, 0)
    correct_heb = hebrew_date.get_hebrew_date_str(dt, check_sunset=False)
    rec_file = config.LOCAL_STAGING_DIR / "(א תשרי תשפ) 12.00.mp3"
    rec_file.write_bytes(make_valid_mp3_bytes())
    os.utime(str(rec_file), (dt.timestamp(), dt.timestamp()))

    expected_new_name = f"({correct_heb}) 12.00.mp3"
    storage.set_recorder_source(rec_file.name, "מקלט 4")
    storage.save_note(expected_new_name, str(config.LOCAL_STAGING_DIR / expected_new_name), "הערה", "בדיקה")

    # Also create an upload file in LOCAL_UPLOAD_DIR
    up_file = config.LOCAL_UPLOAD_DIR / "uploaded_shiur.mp3"
    up_file.write_bytes(make_valid_mp3_bytes())

    res = auth_client.get("/api/lessons/pending")
    assert res.status_code == 200
    payload = res.json()
    assert payload["status"] == "success"

    lessons = {l["filename"]: l for l in payload["lessons"]}
    assert expected_new_name in lessons
    assert not rec_file.exists()
    assert lessons[expected_new_name]["source"] == "recorder"
    assert lessons[expected_new_name]["source_label"] == "מקלט 4"
    assert lessons[expected_new_name]["hebrew_date"] == correct_heb
    assert len(lessons[expected_new_name]["notes"]) == 1

    assert "uploaded_shiur.mp3" in lessons
    assert lessons["uploaded_shiur.mp3"]["source"] == "upload"


def test_set_recorder_source_and_hebrew_date_endpoints(auth_client):
    lesson = config.LOCAL_STAGING_DIR / "(א תשרי תשפז) 09.15.mp3"
    lesson.write_bytes(make_valid_mp3_bytes())
    other = config.LOCAL_STAGING_DIR / "(ב תשרי תשפז) 10.15.mp3"
    other.write_bytes(make_valid_mp3_bytes())

    res_src = auth_client.post(
        "/api/lessons/set_recorder_source",
        data={
            "filename": lesson.name,
            "recorder_label": "RECORDER_2",
            "update_all": "true",
            "old_label": "מקלט שמע",
        },
    )
    assert res_src.status_code == 200
    assert res_src.json()["recorder_label"] == "מקלט 2"
    assert storage.get_recorder_source(lesson.name) == "מקלט 2"
    assert storage.get_recorder_source(other.name) == "מקלט 2"

    res_date = auth_client.post(
        "/api/lessons/set_hebrew_date",
        data={"filename": lesson.name, "hebrew_date": "י כסלו תשפז"},
    )
    assert res_date.status_code == 200
    data_date = res_date.json()
    assert data_date["new_filename"] == "(י כסלו תשפז) 09.15.mp3"
    assert (config.LOCAL_STAGING_DIR / "(י כסלו תשפז) 09.15.mp3").exists()
    assert storage.get_recorder_source("(י כסלו תשפז) 09.15.mp3") == "מקלט 2"

    res_empty_date = auth_client.post(
        "/api/lessons/set_hebrew_date",
        data={"filename": other.name, "hebrew_date": "   "},
    )
    assert res_empty_date.status_code == 400


def test_classify_details_update_and_delete_lesson_lifecycle(auth_client, tmp_path: Path):
    src = config.LOCAL_STAGING_DIR / "(ד כסלו תשפז) 11.00.mp3"
    src.write_bytes(make_valid_mp3_bytes())
    storage.save_note(src.name, str(src), "הערה", "נא לסווג")

    dest_folder = config.DATA_DIR / "sorted" / "הרב אלישיב"
    res_classify = auth_client.post(
        "/api/lessons/classify",
        data={
            "filename": src.name,
            "rabbi_name": "הרב אלישיב",
            "lesson_topic": "בבא קמא",
            "hebrew_date": "ד כסלו תשפז",
            "destination_folder": str(dest_folder),
        },
    )
    assert res_classify.status_code == 200
    classified_name = res_classify.json()["filename"]
    classified_path = Path(res_classify.json()["final_path"])
    assert classified_name == "הרב אלישיב_בבא קמא (ד כסלו תשפז).mp3"
    assert classified_path.exists()
    assert not src.exists()
    assert storage.get_notes_for_file(src.name) == []

    tags = EasyID3(str(classified_path))
    assert tags["artist"] == ["הרב אלישיב"]
    assert tags["title"] == ["בבא קמא"]

    # Create a file with leading track number to verify details_for_edit parsing
    numbered_path = dest_folder / "01הרב אלישיב_שיעור כללי (יב אלול תשפו).mp3"
    numbered_path.write_bytes(make_valid_mp3_bytes())

    res_details = auth_client.get(
        "/api/lessons/details_for_edit",
        params={"filename": numbered_path.name, "original_path": str(numbered_path)},
    )
    assert res_details.status_code == 200
    d_json = res_details.json()
    assert d_json["found"] is True
    assert d_json["rabbi"] == "הרב אלישיב"
    assert d_json["topic"] == "שיעור כללי"
    assert d_json["hebrew_date"] == "יב אלול תשפו"

    # Update lesson + resolve attached note
    edit_note = storage.save_note(numbered_path.name, str(numbered_path), "הערה", "תיקון כותרת")
    res_update = auth_client.post(
        "/api/lessons/update",
        data={
            "source_path": str(numbered_path),
            "rabbi_name": "הרב אלישיב",
            "lesson_topic": "שיעור כללי מתוקן",
            "hebrew_date": "יג אלול תשפו",
            "destination_folder": str(dest_folder),
            "note_id": str(edit_note["id"]),
        },
    )
    assert res_update.status_code == 200
    updated_path = Path(res_update.json()["final_path"])
    assert updated_path.name == "הרב אלישיב_שיעור כללי מתוקן (יג אלול תשפו).mp3"
    assert updated_path.exists()
    assert not numbered_path.exists()
    assert storage.get_notes_for_file(numbered_path.name) == []

    # Delete rejects paths outside allowed roots
    outside_file = tmp_path / "outside_secret.mp3"
    outside_file.write_bytes(make_valid_mp3_bytes())
    res_forbidden = auth_client.post(
        "/api/lessons/delete",
        data={"filename": outside_file.name, "source_path": str(outside_file)},
    )
    assert res_forbidden.status_code == 403
    assert outside_file.exists()

    # Delete succeeds for lesson inside DATA_DIR and resolves open notes
    del_note = storage.save_note(updated_path.name, str(updated_path), "הערה", "למחיקה")
    res_del = auth_client.post(
        "/api/lessons/delete",
        data={"filename": updated_path.name, "source_path": str(updated_path)},
    )
    assert res_del.status_code == 200
    assert res_del.json()["status"] == "success"
    assert not updated_path.exists()
    assert storage.get_notes_for_file(updated_path.name) == []


def test_folders_api_endpoints(auth_client):
    root = config.NETWORK_MOUNT_POINT
    (root / "שנת התשפז" / "הרב דוד").mkdir(parents=True)

    res_list = auth_client.post("/api/folders/list", json={"path": None})
    assert res_list.status_code == 200
    assert [f["name"] for f in res_list.json()["subfolders"]] == ["שנת התשפז"]

    res_search = auth_client.get("/api/folders/search", params={"q": "הרב דוד"})
    assert res_search.status_code == 200
    assert any(r["name"] == "הרב דוד" for r in res_search.json()["results"])

    res_create = auth_client.post(
        "/api/folders/create",
        data={"base_folder": str(root / "שנת התשפז"), "new_folder_name": "הרב משה"},
    )
    assert res_create.status_code == 200
    assert (root / "שנת התשפז" / "הרב משה").is_dir()


# ==========================================
# Audio Streaming & Range Support
# ==========================================

def test_audio_streaming_full_partial_and_invalid_range(auth_client):
    mp3_bytes = make_valid_mp3_bytes(frames=10)
    audio_file = config.LOCAL_STAGING_DIR / "stream_test.mp3"
    audio_file.write_bytes(mp3_bytes)

    # Full request (200)
    res_full = auth_client.get("/api/audio/stream", params={"filename": audio_file.name})
    assert res_full.status_code == 200
    assert res_full.headers["accept-ranges"] == "bytes"
    assert res_full.content == mp3_bytes

    # Partial Range request (206)
    res_part = auth_client.get(
        "/api/audio/stream",
        params={"filename": audio_file.name},
        headers={"Range": "bytes=0-99"},
    )
    assert res_part.status_code == 206
    assert res_part.headers["content-range"] == f"bytes 0-99/{len(mp3_bytes)}"
    assert res_part.headers["content-length"] == "100"
    assert res_part.content == mp3_bytes[:100]

    # Out-of-bounds Range request (416)
    res_oob = auth_client.get(
        "/api/audio/stream",
        params={"filename": audio_file.name},
        headers={"Range": "bytes=999999-"},
    )
    assert res_oob.status_code == 416


# ==========================================
# Rav Tzvi Portal & Protected Streaming
# ==========================================

def test_is_rav_tzvi_name_filtering():
    assert server.is_rav_tzvi_name("הרב צבי קוסטינר") is True
    assert server.is_rav_tzvi_name('מו"ר הרב צבי') is True
    assert server.is_rav_tzvi_name("ראש הישיבה") is True
    assert server.is_rav_tzvi_name("שיעורי הרב צבי") is True

    assert server.is_rav_tzvi_name("הרב צבי יהודה") is False
    assert server.is_rav_tzvi_name("הרב אריה") is False
    assert server.is_rav_tzvi_name("הרב דוד") is False
    assert server.is_rav_tzvi_name("") is False


def test_rav_tzvi_portal_browse_search_docs_and_stream(client, monkeypatch):
    # Populate local Rav Tzvi library
    sub = config.RAV_TZVI_DIR / "תשפז"
    sub.mkdir(parents=True)
    mp3_path = sub / "שיעור_אמונה.mp3"
    mp3_bytes = make_valid_mp3_bytes(frames=10)
    mp3_path.write_bytes(mp3_bytes)
    docx_path = sub / "סיכום_שיעור.docx"
    make_valid_docx(docx_path, title="כותרת ראשית", paragraph="טקסט לבדיקה", table_cell="תא בטבלה")
    txt_path = sub / "הערות.txt"
    txt_path.write_text("שורה ראשונה\nשורה שנייה", encoding="utf-8")

    # Portal HTML page
    res_page = client.get("/rav-tzvi")
    assert res_page.status_code == 200

    # Browse root & subfolder
    res_root = client.get("/api/rav-tzvi/browse")
    assert res_root.status_code == 200
    assert any(f["subpath"] == "local" for f in res_root.json()["folders"])

    res_sub = client.get("/api/rav-tzvi/browse", params={"subpath": "local/תשפז"})
    assert res_sub.status_code == 200
    file_names = {f["filename"] for f in res_sub.json()["files"]}
    assert file_names == {"שיעור_אמונה.mp3", "סיכום_שיעור.docx", "הערות.txt"}

    # Search (< 2 chars returns empty, >= 2 chars returns matches)
    res_short = client.get("/api/rav-tzvi/search", params={"q": "א"})
    assert res_short.status_code == 200
    assert res_short.json()["total_items"] == 0

    res_search = client.get("/api/rav-tzvi/search", params={"q": "אמונה"})
    assert res_search.status_code == 200
    assert len(res_search.json()["files"]) == 1
    assert res_search.json()["files"][0]["filename"] == "שיעור_אמונה.mp3"

    # Tokens & document viewing / streaming protection
    docx_subpath = "local/תשפז/סיכום_שיעור.docx"
    txt_subpath = "local/תשפז/הערות.txt"
    mp3_subpath = "local/תשפז/שיעור_אמונה.mp3"

    docx_token = client.post("/api/rav-tzvi/token", params={"file": docx_subpath}).json()["token"]
    wrong_token = client.post("/api/rav-tzvi/token", params={"file": txt_subpath}).json()["token"]
    mp3_token = client.post("/api/rav-tzvi/token", params={"file": mp3_subpath}).json()["token"]

    # Invalid / missing / mismatched / expired tokens return 403 (mismatch also revokes token)
    assert client.get("/api/rav-tzvi/view-doc", params={"file": docx_subpath}).status_code == 403
    assert client.get("/api/rav-tzvi/view-doc", params={"file": docx_subpath, "token": wrong_token}).status_code == 403
    assert wrong_token not in server.STREAMING_TOKENS
    assert client.get("/api/rav-tzvi/stream", params={"file": mp3_subpath, "token": "bad"}).status_code == 403

    txt_token = client.post("/api/rav-tzvi/token", params={"file": txt_subpath}).json()["token"]

    expired_token = "expired-tok"
    server.STREAMING_TOKENS[expired_token] = {
        "file": mp3_subpath,
        "expires": datetime.now() - timedelta(minutes=1),
    }
    assert client.get("/api/rav-tzvi/stream", params={"file": mp3_subpath, "token": expired_token}).status_code == 403

    # Valid DOCX view-doc & protected stream
    res_doc = client.get("/api/rav-tzvi/view-doc", params={"file": docx_subpath, "token": docx_token})
    assert res_doc.status_code == 200
    assert res_doc.json()["type"] == "html"
    assert "כותרת ראשית" in res_doc.json()["html"]
    assert "טקסט לבדיקה" in res_doc.json()["html"]

    res_doc_stream = client.get("/api/rav-tzvi/stream", params={"file": docx_subpath, "token": docx_token})
    assert res_doc_stream.status_code == 200
    assert "text/html" in res_doc_stream.headers["content-type"]
    assert "לצפייה בלבד" in res_doc_stream.text

    # Valid TXT view-doc
    res_txt = client.get("/api/rav-tzvi/view-doc", params={"file": txt_subpath, "token": txt_token})
    assert res_txt.status_code == 200
    assert "שורה ראשונה" in res_txt.json()["html"]

    # Valid MP3 protected stream with Range header
    res_mp3 = client.get(
        "/api/rav-tzvi/stream",
        params={"file": mp3_subpath, "token": mp3_token},
        headers={"Range": "bytes=0-49"},
    )
    assert res_mp3.status_code == 206
    assert res_mp3.content == mp3_bytes[:50]

    # Built-in XML fallback in docx_to_html when mammoth fails
    import mammoth
    monkeypatch.setattr(mammoth, "convert_to_html", lambda _: (_ for _ in ()).throw(RuntimeError("force fallback")))
    fallback_html = server.docx_to_html(docx_path)
    assert "<h1 class='doc-heading'" in fallback_html
    assert "<u><em><strong>טקסט לבדיקה</strong></em></u>" in fallback_html
    assert "<table class='doc-table'>" in fallback_html
    assert "תא בטבלה" in fallback_html

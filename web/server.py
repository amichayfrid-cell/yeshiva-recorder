import os
import re
import shutil
import mimetypes
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Request, Form, Depends, HTTPException, status, Query
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

import config
from core.hebrew_date import get_hebrew_date_str
from core.file_manager import apply_id3_tags, get_unique_filepath
from web import storage

app = FastAPI(title="מערכת מיון שיעורי הישיבה", version="2.0.0")

BASE_WEB_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_WEB_DIR / "templates"
STATIC_DIR = BASE_WEB_DIR / "static"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "1234")
COOKIE_NAME = "yeshiva_admin_auth"

def is_authenticated(request: Request) -> bool:
    return request.cookies.get(COOKIE_NAME) == ADMIN_PASSWORD

def get_sorting_dir() -> Path:
    if config.NETWORK_TARGET_DIR.exists():
        return config.NETWORK_TARGET_DIR
    return config.LOCAL_STAGING_DIR

def stream_audio_range(file_path: Path, range_header: Optional[str] = None):
    file_size = file_path.stat().st_size
    content_type, _ = mimetypes.guess_type(str(file_path))
    content_type = content_type or "audio/mpeg"

    start = 0
    end = file_size - 1

    if range_header:
        match = re.match(r"bytes=(\d+)-(\d*)", range_header)
        if match:
            start = int(match.group(1))
            if match.group(2):
                end = int(match.group(2))

    length = end - start + 1

    def iterfile():
        with open(file_path, "rb") as f:
            f.seek(start)
            remaining = length
            chunk_size = 64 * 1024
            while remaining > 0:
                read_size = min(chunk_size, remaining)
                data = f.read(read_size)
                if not data:
                    break
                remaining -= len(data)
                yield data

    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(length),
        "Content-Type": content_type,
    }
    return StreamingResponse(iterfile(), status_code=206 if range_header else 200, headers=headers)

# --- Routes ---

@app.get("/", response_class=HTMLResponse)
def index():
    return RedirectResponse(url="/admin")

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, error: Optional[str] = None):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": error}
    )

@app.post("/login")
def process_login(password: str = Form(...)):
    if password == ADMIN_PASSWORD:
        response = RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)
        # Session cookie: deleted when browser is closed
        response.set_cookie(key=COOKIE_NAME, value=ADMIN_PASSWORD, httponly=True)
        return response
    return RedirectResponse(url="/login?error=1", status_code=status.HTTP_302_FOUND)

@app.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key=COOKIE_NAME)
    return response

@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/login")
    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={}
    )

@app.get("/student", response_class=HTMLResponse)
def student_feedback_page(request: Request, file: Optional[str] = None):
    # Fix backslashes for Linux basename extraction
    clean_file = file.replace('\\', '/') if file else ""
    filename = os.path.basename(clean_file) if clean_file else ""
    return templates.TemplateResponse(
        request=request,
        name="student.html",
        context={
            "original_file": file or "",
            "filename": filename
        }
    )

@app.post("/api/student/notes")
def submit_student_note(
    filename: str = Form(...),
    original_path: str = Form(""),
    description: str = Form(...),
    student_name: Optional[str] = Form(None)
):
    note = storage.save_note(
        filename=filename,
        original_path=original_path,
        note_type="הערה",
        description=description,
        student_name=student_name
    )
    return JSONResponse({"status": "success", "note": note})

@app.get("/api/lessons/pending")
def list_pending_lessons(request: Request):
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    sorting_dir = get_sorting_dir()
    lessons = []

    if sorting_dir.exists():
        for f in sorted(sorting_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
            if f.is_file() and f.suffix.lower() in config.USB_AUDIO_EXTENSIONS:
                file_dt = datetime.fromtimestamp(f.stat().st_mtime)
                hebrew_date = get_hebrew_date_str(file_dt)
                notes = storage.get_notes_for_file(f.name)
                
                lessons.append({
                    "filename": f.name,
                    "size_bytes": f.stat().st_size,
                    "size_mb": round(f.stat().st_size / (1024 * 1024), 1),
                    "created_time": file_dt.strftime("%H:%M"),
                    "hebrew_date": hebrew_date,
                    "notes": notes
                })

    return JSONResponse({"status": "success", "lessons": lessons, "target_dir": str(sorting_dir)})

@app.get("/api/audio/stream")
def stream_audio(request: Request, filename: str = Query(...)):
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    sorting_dir = get_sorting_dir()
    file_path = sorting_dir / filename

    if not file_path.exists() or not file_path.is_file():
        p = Path(filename)
        if p.exists() and p.is_file():
            file_path = p
        else:
            raise HTTPException(status_code=404, detail="File not found")

    range_header = request.headers.get("range")
    return stream_audio_range(file_path, range_header)

class FolderListRequest(BaseModel):
    path: Optional[str] = None

@app.post("/api/folders/list")
def api_list_folders_post(request: Request, body: FolderListRequest):
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    data = storage.list_direct_subfolders(body.path)
    return JSONResponse({"status": "success", **data})

@app.post("/api/folders/create")
def api_create_folder(request: Request, base_folder: str = Form(...), new_folder_name: str = Form(...)):
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        new_path = storage.create_new_folder(base_folder, new_folder_name)
        return JSONResponse({"status": "success", "new_folder_path": new_path})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=400)

@app.post("/api/lessons/classify")
def classify_lesson(
    request: Request,
    filename: str = Form(...),
    rabbi_name: str = Form(...),
    lesson_topic: Optional[str] = Form(""),
    hebrew_date: str = Form(...),
    destination_folder: str = Form(...)
):
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    sorting_dir = get_sorting_dir()
    source_file = sorting_dir / filename

    if not source_file.exists():
        raise HTTPException(status_code=404, detail="Source file not found")

    dest_dir = Path(destination_folder)
    if not dest_dir.exists():
        dest_dir.mkdir(parents=True, exist_ok=True)

    ext = source_file.suffix.lower()
    clean_rabbi = rabbi_name.strip().replace("/", "-")
    clean_topic = lesson_topic.strip().replace("/", "-")
    clean_date = hebrew_date.strip().replace("/", "-")

    if clean_topic:
        final_filename = f"{clean_rabbi}_{clean_topic}_({clean_date}){ext}"
    else:
        final_filename = f"{clean_rabbi}_({clean_date}){ext}"

    unique_dest_path = get_unique_filepath(dest_dir, final_filename)

    # 1. Apply ID3 tags in-place
    metadata = {
        "rabbi": clean_rabbi,
        "topic": clean_topic,
        "status": "classified"
    }
    try:
        apply_id3_tags(source_file, metadata, clean_date)
    except Exception as e:
        print(f"[Classify] ID3 tagging skipped: {e}")

    # 2. Instant rename/move within same CIFS filesystem (0.05s)
    try:
        shutil.move(str(source_file), str(unique_dest_path))
    except Exception as e:
        # Fallback
        shutil.copy2(str(source_file), str(unique_dest_path))
        source_file.unlink(missing_ok=True)

    # 3. Mark notes as resolved
    for note in storage.get_notes_for_file(filename):
        storage.update_note_status(note["id"], "resolved")

    return JSONResponse({
        "status": "success",
        "final_path": str(unique_dest_path),
        "filename": unique_dest_path.name
    })

@app.get("/api/notes/all")
def get_all_notes(request: Request):
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    notes = storage.get_notes_data()
    return JSONResponse({"status": "success", "notes": notes})

@app.post("/api/notes/status")
def change_note_status(request: Request, note_id: int = Form(...), status: str = Form(...)):
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    success = storage.update_note_status(note_id, status)
    return JSONResponse({"status": "success" if success else "error"})

def locate_lesson_file(filename: str, original_path: Optional[str] = None) -> Optional[Path]:
    """Locates an audio file anywhere in the sorting directory or network share."""
    clean_fn = os.path.basename(filename.replace('\\', '/'))
    
    # 1. Check sorting dir first
    sorting_dir = get_sorting_dir()
    p = sorting_dir / clean_fn
    if p.exists() and p.is_file():
        return p

    # 2. Check if filename itself is an absolute path that exists
    p_direct = Path(filename)
    if p_direct.exists() and p_direct.is_file():
        return p_direct
        
    # 3. Check original_path if provided
    if original_path:
        p_orig = Path(original_path.replace('\\', '/'))
        if p_orig.exists() and p_orig.is_file():
            return p_orig

    # 4. Search within NETWORK_MOUNT_POINT / LOCAL_STAGING_DIR
    root = config.NETWORK_MOUNT_POINT if config.NETWORK_MOUNT_POINT.exists() else config.LOCAL_STAGING_DIR
    if root.exists():
        for dirpath, _, filenames in os.walk(root):
            if clean_fn in filenames:
                return Path(dirpath) / clean_fn
                
    return None

@app.get("/api/lessons/details_for_edit")
def get_lesson_details_for_edit(request: Request, filename: str = Query(...), note_id: Optional[int] = Query(None)):
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    file_path = locate_lesson_file(filename)
    if not file_path or not file_path.exists():
        return JSONResponse({"status": "success", "found": False})
    
    name_no_ext = file_path.stem
    rabbi = ""
    topic = ""
    hebrew_date = ""
    
    # Try parsing date in parentheses: (יב אלול תשפו)
    date_match = re.search(r"\(([^)]+)\)$", name_no_ext)
    if date_match:
        hebrew_date = date_match.group(1).replace("_", " ")
        name_no_ext = name_no_ext[:date_match.start()].rstrip("_ ")
        
    parts = name_no_ext.split("_")
    if len(parts) >= 2:
        rabbi = parts[0].strip()
        topic = "_".join(parts[1:]).strip()
    elif len(parts) == 1:
        rabbi = parts[0].strip()

    if not hebrew_date:
        file_dt = datetime.fromtimestamp(file_path.stat().st_mtime)
        hebrew_date = get_hebrew_date_str(file_dt)

    root_str = str(config.NETWORK_MOUNT_POINT if config.NETWORK_MOUNT_POINT.exists() else config.LOCAL_STAGING_DIR)
    try:
        rel_folder = os.path.relpath(str(file_path.parent), root_str)
        if rel_folder == ".":
            rel_folder = "ראשי (שרת הישיבה)"
    except Exception:
        rel_folder = str(file_path.parent)

    return JSONResponse({
        "status": "success",
        "found": True,
        "filename": file_path.name,
        "full_path": str(file_path),
        "parent_folder": str(file_path.parent),
        "parent_folder_rel": rel_folder,
        "rabbi": rabbi,
        "topic": topic,
        "hebrew_date": hebrew_date
    })

@app.post("/api/lessons/update")
def update_lesson(
    request: Request,
    source_path: str = Form(...),
    rabbi_name: str = Form(...),
    lesson_topic: Optional[str] = Form(""),
    hebrew_date: str = Form(...),
    destination_folder: str = Form(...),
    note_id: Optional[int] = Form(None)
):
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    source_file = Path(source_path)
    if not source_file.exists() or not source_file.is_file():
        raise HTTPException(status_code=404, detail="Source file not found")

    dest_dir = Path(destination_folder)
    dest_dir.mkdir(parents=True, exist_ok=True)

    ext = source_file.suffix.lower()
    clean_rabbi = rabbi_name.strip().replace("/", "-")
    clean_topic = lesson_topic.strip().replace("/", "-") if lesson_topic else ""
    clean_date = hebrew_date.strip().replace("/", "-")

    if clean_topic:
        final_filename = f"{clean_rabbi}_{clean_topic}_({clean_date}){ext}"
    else:
        final_filename = f"{clean_rabbi}_({clean_date}){ext}"

    unique_dest_path = get_unique_filepath(dest_dir, final_filename)

    # 1. Update ID3 tags
    metadata = {
        "rabbi": clean_rabbi,
        "topic": clean_topic,
        "status": "classified"
    }
    try:
        apply_id3_tags(source_file, metadata, clean_date)
    except Exception as e:
        print(f"[Update Lesson] ID3 tagging skipped: {e}")

    # 2. Rename / Move
    try:
        shutil.move(str(source_file), str(unique_dest_path))
    except Exception as e:
        shutil.copy2(str(source_file), str(unique_dest_path))
        source_file.unlink(missing_ok=True)

    # 3. Mark note as resolved if provided
    if note_id:
        storage.update_note_status(note_id, "resolved")
    
    # Also resolve notes for old source file name
    for note in storage.get_notes_for_file(source_file.name):
        storage.update_note_status(note["id"], "resolved")

    return JSONResponse({
        "status": "success",
        "final_path": str(unique_dest_path),
        "filename": unique_dest_path.name
    })

@app.post("/api/lessons/delete")
def delete_lesson(request: Request, filename: str = Form(...)):
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    clean_fn = os.path.basename(filename.replace('\\', '/'))
    sorting_dir = get_sorting_dir()
    file_path = sorting_dir / clean_fn

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    try:
        file_path.unlink()
        # Resolve any open notes for this file
        for note in storage.get_notes_for_file(clean_fn):
            storage.update_note_status(note["id"], "resolved")
        return JSONResponse({"status": "success", "message": "הקובץ נמחק בהצלחה"})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

import os
import re
import shutil
import mimetypes
from pathlib import Path
import secrets
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple

from fastapi import FastAPI, Request, Form, Depends, HTTPException, status, Query
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, RedirectResponse, FileResponse, Response
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

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Audio8")
COOKIE_NAME = "yeshiva_session"

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
    response.delete_cookie(key="yeshiva_admin_auth")
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
        entries = []
        try:
            for p in sorting_dir.iterdir():
                try:
                    # Ignore and clean any hidden/temporary/CIFS files (like .__smb0001)
                    if p.name.startswith(".") or "smb" in p.name.lower():
                        try:
                            p.unlink(missing_ok=True)
                        except Exception:
                            pass
                        continue

                    if p.is_file() and p.suffix.lower() in config.USB_AUDIO_EXTENSIONS:
                        st = p.stat()
                        entries.append((p, st))
                except (OSError, FileNotFoundError, PermissionError):
                    continue
        except (OSError, FileNotFoundError, PermissionError):
            pass

        # Sort safely by mtime
        entries.sort(key=lambda item: item[1].st_mtime, reverse=True)

        for f, st in entries:
            try:
                file_dt = datetime.fromtimestamp(st.st_mtime)
                hebrew_date = get_hebrew_date_str(file_dt)
                notes = storage.get_notes_for_file(f.name)
                
                lessons.append({
                    "filename": f.name,
                    "size_bytes": st.st_size,
                    "size_mb": round(st.st_size / (1024 * 1024), 1),
                    "created_time": file_dt.strftime("%H:%M"),
                    "hebrew_date": hebrew_date,
                    "notes": notes
                })
            except Exception:
                continue

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
        
        # Clean any CIFS temporary files in sorting dir
        for f in sorting_dir.iterdir():
            if f.is_file() and ("smb" in f.name.lower()):
                try:
                    f.unlink(missing_ok=True)
                except Exception:
                    pass

        # Resolve any open notes for this file
        for note in storage.get_notes_for_file(clean_fn):
            storage.update_note_status(note["id"], "resolved")
        return JSONResponse({"status": "success", "message": "הקובץ נמחק בהצלחה"})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

# ==========================================
# Rav Tzvi Protected Streaming Logic
# ==========================================
STREAMING_TOKENS = {}

@app.post("/api/rav-tzvi/token")
def get_stream_token(file: str = Query(..., description="Relative file subpath")):
    import secrets
    from datetime import datetime, timedelta
    token = secrets.token_urlsafe(16)
    # Token valid for 30 seconds
    STREAMING_TOKENS[token] = {"file": file, "expires": datetime.now() + timedelta(seconds=30)}
    
    # Cleanup old tokens
    now = datetime.now()
    expired = [t for t, data in STREAMING_TOKENS.items() if data["expires"] < now]
    for t in expired:
        STREAMING_TOKENS.pop(t, None)
        
    return {"token": token}

def find_rav_tzvi_in_folder(folder: Path) -> Optional[Path]:
    """Finds Rav Tzvi Kostiner's folder inside a given semester or year folder."""
    # Exclude non-semester collections
    if "רבנים שונים" in folder.name or "הגברת החירות" in folder.name:
        return None

    # 1. Exact canonical path: folder / "רבני הישיבה" / "הרב צבי קוסטינר"
    cand = folder / "רבני הישיבה" / "הרב צבי קוסטינר"
    if cand.exists() and cand.is_dir():
        return cand
        
    # 2. Check inside "רבני הישיבה" for Kostiner specifically (prevent 'הרב צבי יהודה')
    cand2 = folder / "רבני הישיבה"
    if cand2.exists() and cand2.is_dir():
        for sub in cand2.iterdir():
            if sub.is_dir() and "קוסטינר" in sub.name and "יהודה" not in sub.name:
                return sub

    # 3. Direct folder search for Kostiner specifically
    try:
        for sub in folder.iterdir():
            if sub.is_dir() and "קוסטינר" in sub.name and "יהודה" not in sub.name:
                return sub
    except Exception:
        pass
            
    return None

def find_rav_tzvi_archive(base_mount: Path) -> Optional[Path]:
    """Finds Rav Tzvi's archive folder on the network share."""
    archive_base = base_mount / "ארכיון שיעורי הישיבה"
    if not archive_base.exists():
        return None
        
    p1 = archive_base / "רבני הישיבה" / "הרב צבי קוסטינר - ניהול בלבד"
    if p1.exists() and p1.is_dir():
        return p1
        
    p2 = archive_base / "רבני הישיבה" / "הרב צבי קוסטינר"
    if p2.exists() and p2.is_dir():
        return p2
        
    try:
        rabbi_dir = archive_base / "רבני הישיבה"
        if rabbi_dir.exists():
            for d in rabbi_dir.iterdir():
                if d.is_dir() and "קוסטינר" in d.name and "יהודה" not in d.name:
                    return d
    except Exception:
        pass
    return None

def get_rav_tzvi_sources() -> Dict[str, Dict[str, Any]]:
    """
    Dynamically scans the network share to discover Rav Tzvi's current zman folder
    (e.g., 'אלול התשפ''ו' or whatever it changes to) and the Archive folder.
    """
    sources = {}
    base_mount = config.NETWORK_MOUNT_POINT if config.NETWORK_MOUNT_POINT.exists() else config.LOCAL_STAGING_DIR
    
    EXCLUDED = {
        "ארכיון שיעורי הישיבה", 
        "שיעורים למיון", 
        "אחראי שמע", 
        "רבנים שונים",
        "על הגברת החירות [פלאפונים וכו'] - רבנים שונים",
        "lost+found", 
        "$RECYCLE.BIN", 
        "System Volume Information"
    }
    if base_mount.exists() and base_mount.is_dir():
        for item in sorted(base_mount.iterdir(), key=lambda x: x.name, reverse=True):
            if item.is_dir() and not item.name.startswith(".") and item.name not in EXCLUDED and "רבנים שונים" not in item.name:
                rt_folder = find_rav_tzvi_in_folder(item)
                if rt_folder:
                    slug = re.sub(r'[^a-zA-Z0-9_\u0590-\u05FF]', '_', item.name).strip("_")
                    key = f"current_{slug}"
                    sources[key] = {
                        "display_name": f"שיעורים שוטפים ({item.name})",
                        "path": rt_folder
                    }
                    
    arch = find_rav_tzvi_archive(base_mount)
    if arch:
        sources["archive"] = {
            "display_name": "ארכיון שיעורי הרב צבי",
            "path": arch
        }
        
    if not sources:
        local_dir = config.RAV_TZVI_DIR
        local_dir.mkdir(parents=True, exist_ok=True)
        sources["local"] = {
            "display_name": "שיעורי הרב צבי",
            "path": local_dir
        }
        
    return sources

def resolve_rav_tzvi_path(subpath: str = "") -> Tuple[Optional[Path], Optional[str], Optional[Path]]:
    """
    Resolves virtual subpath to an actual filesystem Path.
    Returns: (actual_path, root_key, base_root_path)
    If subpath is empty, returns (None, None, None) which signals the Root View.
    """
    if not subpath or subpath.strip() == "" or subpath == ".":
        return None, None, None
        
    clean_sub = os.path.normpath(subpath).replace("\\", "/").strip("/")
    parts = clean_sub.split("/")
    root_key = parts[0]
    rel_sub = "/".join(parts[1:])
    
    sources = get_rav_tzvi_sources()
    if root_key not in sources:
        raise HTTPException(status_code=404, detail="Library section not found")
        
    base = sources[root_key]["path"].resolve()
    if not rel_sub:
        return base, root_key, base
        
    target = (base / rel_sub).resolve()
    if not str(target).startswith(str(base)):
        raise HTTPException(status_code=400, detail="Invalid path traversal")
        
    return target, root_key, base

@app.get("/api/rav-tzvi/browse")
def browse_rav_tzvi(subpath: str = Query("", description="Relative folder subpath")):
    """
    Browses Rav Tzvi Kostiner's protected library in an Explorer-like structure.
    Returns breadcrumbs, folders, and playable audio files.
    """
    sources = get_rav_tzvi_sources()
    target_path, root_key, base_path = resolve_rav_tzvi_path(subpath)
    
    # 1. Top-Level Root View (Sections: Current Semester + Archive)
    if target_path is None:
        folders = []
        for key, info in sources.items():
            p = info["path"]
            audio_count = 0
            subfolder_count = 0
            if p.exists():
                try:
                    audio_count = len([f for f in p.iterdir() if f.is_file() and f.suffix.lower() in config.USB_AUDIO_EXTENSIONS])
                    subfolder_count = len([f for f in p.iterdir() if f.is_dir() and not f.name.startswith(".")])
                except Exception:
                    pass
            folders.append({
                "name": info["display_name"],
                "subpath": key,
                "audio_count": audio_count,
                "subfolder_count": subfolder_count
            })
        return {
            "current_subpath": "",
            "breadcrumbs": [{"name": "שיעורי הרב צבי", "subpath": ""}],
            "folders": folders,
            "files": [],
            "total_items": len(folders)
        }

    # 2. Inside a section or folder
    if not target_path.exists() or not target_path.is_dir():
        raise HTTPException(status_code=404, detail="Directory not found")

    rel_inside_base = target_path.relative_to(base_path).as_posix()
    if rel_inside_base == ".":
        rel_inside_base = ""

    root_display = sources[root_key]["display_name"]
    breadcrumbs = [
        {"name": "שיעורי הרב צבי", "subpath": ""},
        {"name": root_display, "subpath": root_key}
    ]
    if rel_inside_base:
        parts = rel_inside_base.split("/")
        accumulated = [root_key]
        for part in parts:
            accumulated.append(part)
            breadcrumbs.append({
                "name": part,
                "subpath": "/".join(accumulated)
            })

    folders = []
    files = []

    for item in sorted(target_path.iterdir(), key=lambda x: x.name):
        if item.name.startswith(".") or item.name == "Thumbs.db":
            continue
        rel_to_base = item.relative_to(base_path).as_posix()
        item_subpath = f"{root_key}/{rel_to_base}"
        if item.is_dir():
            audio_count = 0
            subfolder_count = 0
            try:
                audio_count = len([f for f in item.iterdir() if f.is_file() and f.suffix.lower() in config.USB_AUDIO_EXTENSIONS])
                subfolder_count = len([f for f in item.iterdir() if f.is_dir() and not f.name.startswith(".")])
            except Exception:
                pass
            folders.append({
                "name": item.name,
                "subpath": item_subpath,
                "audio_count": audio_count,
                "subfolder_count": subfolder_count
            })
        elif item.is_file() and item.suffix.lower() in config.USB_AUDIO_EXTENSIONS:
            stat = item.stat()
            files.append({
                "filename": item.name,
                "subpath": item_subpath,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
            })

    current_sp = f"{root_key}/{rel_inside_base}".rstrip("/")
    return {
        "current_subpath": current_sp,
        "breadcrumbs": breadcrumbs,
        "folders": folders,
        "files": files,
        "total_items": len(folders) + len(files)
    }

@app.get("/api/rav-tzvi/search")
def search_rav_tzvi(q: str = Query("", description="Search query across all folders")):
    """
    Recursively searches across all Rav Tzvi library sections matching query q.
    """
    query = q.strip().lower()
    if not query:
        return {"query": q, "folders": [], "files": [], "total_items": 0}

    sources = get_rav_tzvi_sources()
    folders = []
    files = []

    for root_key, info in sources.items():
        base = info["path"]
        if not base.exists():
            continue
        try:
            for item in base.rglob("*"):
                if item.name.startswith(".") or item.name == "Thumbs.db":
                    continue
                rel_posix = item.relative_to(base).as_posix()
                item_subpath = f"{root_key}/{rel_posix}"
                if query in item.name.lower():
                    folder_rel = "/".join(rel_posix.split("/")[:-1])
                    display_folder = f"{info['display_name']} / {folder_rel}" if folder_rel else info['display_name']
                    if item.is_dir():
                        audio_count = 0
                        try:
                            audio_count = len([f for f in item.iterdir() if f.is_file() and f.suffix.lower() in config.USB_AUDIO_EXTENSIONS])
                        except Exception:
                            pass
                        folders.append({
                            "name": item.name,
                            "subpath": item_subpath,
                            "folder_path": display_folder,
                            "audio_count": audio_count
                        })
                    elif item.is_file() and item.suffix.lower() in config.USB_AUDIO_EXTENSIONS:
                        stat = item.stat()
                        files.append({
                            "filename": item.name,
                            "subpath": item_subpath,
                            "folder_path": display_folder,
                            "size_mb": round(stat.st_size / (1024 * 1024), 2),
                            "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
                        })
                if len(folders) + len(files) >= 150:
                    break
        except Exception as e:
            print(f"[Search Error in {root_key}]: {e}")

    return {
        "query": q,
        "folders": folders,
        "files": files,
        "total_items": len(folders) + len(files)
    }

@app.get("/api/rav-tzvi/stream")
def stream_rav_tzvi(file: str = Query(..., description="Relative file subpath"), token: str = Query(None), request: Request = None):
    """
    Protected streaming of Rav Tzvi shiurim directly from disk with Range Header support.
    Disallows external downloads and supports responsive web playback.
    """
    if not token or token not in STREAMING_TOKENS:
        raise HTTPException(status_code=403, detail="Invalid or missing stream token")
        
    token_data = STREAMING_TOKENS[token]
    if token_data["file"] != file or token_data["expires"] < datetime.now():
        STREAMING_TOKENS.pop(token, None)
        raise HTTPException(status_code=403, detail="Token expired or mismatched")
        
    dest = request.headers.get("Sec-Fetch-Dest", "")
    if dest and dest not in ("audio", "empty", "document"):
        raise HTTPException(status_code=403, detail="Direct downloading is blocked")

    file_path, _, _ = resolve_rav_tzvi_path(file)
    if not file_path or not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Audio file not found")

    file_size = file_path.stat().st_size
    mime_type, _ = mimetypes.guess_type(str(file_path))
    mime_type = mime_type or "audio/mpeg"

    range_header = request.headers.get("range") if request else None

    if not range_header:
        response = FileResponse(path=file_path, media_type=mime_type, filename=file_path.name)
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return response

    try:
        byte_range = range_header.replace("bytes=", "").split("-")
        start = int(byte_range[0])
        end = int(byte_range[1]) if byte_range[1] else file_size - 1
        end = min(end, file_size - 1)
        length = end - start + 1

        with open(file_path, "rb") as f:
            f.seek(start)
            data = f.read(length)

        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(length),
            "Content-Type": mime_type,
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"
        }
        return Response(content=data, status_code=206, headers=headers)
    except Exception:
        response = FileResponse(path=file_path, media_type=mime_type, filename=file_path.name)
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return response

@app.get("/rav-tzvi")
def rav_tzvi_page():
    """Serves the Explorer-like Protected Streamer for Rav Tzvi Kostiner's Shiurim."""
    for candidate in [STATIC_DIR / "rav_tzvi.html", TEMPLATES_DIR / "rav_tzvi.html"]:
        if candidate.exists():
            return FileResponse(str(candidate))
    return HTMLResponse("<h1>Rav Tzvi Library Loading... (rav_tzvi.html not found)</h1>", status_code=404)

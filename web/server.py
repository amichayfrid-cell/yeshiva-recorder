import os
import secrets
import mimetypes
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException, Depends, Header, Query, Request, status
from fastapi.responses import FileResponse, Response, RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import config
from core import notes_manager
from core.hebrew_date import get_hebrew_date_str
from core.file_manager import safe_move, get_unique_filepath, record_history, apply_id3_tags
from core.network_share import is_share_mounted, get_network_target_dir

# Initialize FastAPI App
app = FastAPI(
    title="Yeshiva Audio Recorder & Sorter API",
    description="Backend API for Audio Management, Streaming, and Student Feedback",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session token store (simple, secure local auth)
ACTIVE_TOKENS: Dict[str, datetime] = {}
TOKEN_EXPIRY_HOURS = 24

def cleanup_expired_tokens():
    now = datetime.now()
    expired = [t for t, exp in ACTIVE_TOKENS.items() if exp < now]
    for t in expired:
        ACTIVE_TOKENS.pop(t, None)

def require_admin(authorization: Optional[str] = Header(None)) -> bool:
    """Dependency checking for valid Bearer token."""
    cleanup_expired_tokens()
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required"
        )
    token = authorization.split(" ")[1]
    if token not in ACTIVE_TOKENS or ACTIVE_TOKENS[token] < datetime.now():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token"
        )
    return True

# Pydantic Request Models
class LoginRequest(BaseModel):
    password: str

class NoteCreateRequest(BaseModel):
    filename: str
    content: str
    filepath: Optional[str] = ""

class NoteResolveRequest(BaseModel):
    resolution_note: Optional[str] = ""

class SortFileRequest(BaseModel):
    filename: str
    current_location: Optional[str] = ""
    rabbi_name: str
    topic: str
    hebrew_date: Optional[str] = None
    note_id_to_resolve: Optional[str] = None

# Helper to find file across relevant storage locations
def locate_audio_file(filename: str) -> Optional[Path]:
    """Finds the actual audio file path across storage locations."""
    clean_name = Path(filename).name
    search_dirs = [
        config.LOCAL_BUFFER_DIR,
        config.INCOMING_DIR,
        config.NEEDS_REVIEW_DIR,
        config.SORTED_DIR,
    ]
    
    if config.USE_NETWORK_SHARE and is_share_mounted():
        net_dir = config.SMB_MOUNT_POINT / config.SMB_TARGET_SUBDIR_NAME
        if net_dir.exists():
            search_dirs.insert(0, net_dir)

    for base_dir in search_dirs:
        if not base_dir.exists():
            continue
        candidate = base_dir / clean_name
        if candidate.exists() and candidate.is_file():
            return candidate
        # Recursive search in sorted subfolders
        matches = list(base_dir.rglob(clean_name))
        if matches and matches[0].is_file():
            return matches[0]

    return None

# ==========================================
# Authentication Endpoints
# ==========================================
@app.post("/api/auth/login")
def login(req: LoginRequest):
    """Logs in admin with password and returns session token."""
    if req.password == config.ADMIN_PASSWORD:
        token = secrets.token_hex(24)
        ACTIVE_TOKENS[token] = datetime.now() + timedelta(hours=TOKEN_EXPIRY_HOURS)
        return {"success": True, "token": token, "expires_in_hours": TOKEN_EXPIRY_HOURS}
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password")

@app.get("/api/auth/check")
def check_auth(authenticated: bool = Depends(require_admin)):
    """Validates session token."""
    return {"authenticated": True}

# ==========================================
# Audio Streaming Endpoint (Range Header Support)
# ==========================================
@app.get("/api/audio/stream")
def stream_audio(file: str = Query(..., description="Filename or relative path to stream"), request: Request = None):
    """
    Streams audio directly from disk with HTTP Range support.
    Zero duplicate files, fast playback, and seeking enabled!
    """
    file_path = locate_audio_file(file)
    if not file_path or not file_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")

    file_size = file_path.stat().st_size
    mime_type, _ = mimetypes.guess_type(str(file_path))
    mime_type = mime_type or "audio/mpeg"

    range_header = request.headers.get("range") if request else None

    if not range_header:
        # Full content response
        return FileResponse(path=file_path, media_type=mime_type, filename=file_path.name)

    # Partial content (206) for streaming & instant seeking
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
        }
        return Response(content=data, status_code=206, headers=headers)
    except Exception as e:
        return FileResponse(path=file_path, media_type=mime_type, filename=file_path.name)

# ==========================================
# Notes & Alerts API (Student & Admin)
# ==========================================
@app.post("/api/notes")
def create_note(req: NoteCreateRequest):
    """Public endpoint for students to leave feedback/corrections on a recording."""
    if not req.filename or not req.content:
        raise HTTPException(status_code=400, detail="Filename and content are required")
    note = notes_manager.add_note(
        filename=req.filename,
        content=req.content,
        filepath=req.filepath
    )
    return {"success": True, "note": note}

@app.get("/api/notes")
def list_notes(status_filter: Optional[str] = Query(None, alias="status"), authenticated: bool = Depends(require_admin)):
    """Admin endpoint to list all student feedback notes."""
    notes = notes_manager.get_notes(status=status_filter)
    return {"notes": notes}

@app.post("/api/notes/{note_id}/resolve")
def resolve_note_endpoint(note_id: str, req: NoteResolveRequest, authenticated: bool = Depends(require_admin)):
    """Admin endpoint to mark a note as resolved."""
    success = notes_manager.resolve_note(note_id, resolution_note=req.resolution_note or "")
    if not success:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"success": True, "note_id": note_id}

@app.delete("/api/notes/{note_id}")
def delete_note_endpoint(note_id: str, authenticated: bool = Depends(require_admin)):
    """Admin endpoint to delete a note."""
    success = notes_manager.delete_note(note_id)
    if not success:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"success": True, "note_id": note_id}

# ==========================================
# Queue & File Sorting API (Admin)
# ==========================================
@app.get("/api/rabbis")
def get_rabbis():
    """Returns the list of known rabbis configured in the system."""
    return {"rabbis": config.KNOWN_RABBIS}

@app.get("/api/files/queue")
def get_sorting_queue(authenticated: bool = Depends(require_admin)):
    """
    Returns files currently waiting in the sorting queue (local buffer, needs_review, or network share).
    Each file includes its attached notes count and details.
    """
    queue_files = []
    seen_names = set()

    sources = []
    if config.USE_NETWORK_SHARE and is_share_mounted():
        net_dir = config.SMB_MOUNT_POINT / config.SMB_TARGET_SUBDIR_NAME
        if net_dir.exists():
            sources.append((net_dir, "שיעורים למיון (שרת ישיבה)"))
    
    sources.extend([
        (config.LOCAL_BUFFER_DIR, "חיץ מקומי"),
        (config.NEEDS_REVIEW_DIR, "לסיווג ידני מקומי"),
        (config.INCOMING_DIR, "קליטה מקומית"),
    ])

    for dir_path, location_label in sources:
        if not dir_path.exists():
            continue
        for file_path in dir_path.iterdir():
            if file_path.is_file() and not file_path.name.startswith("."):
                if file_path.suffix.lower() in {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".wma"}:
                    if file_path.name in seen_names:
                        continue
                    seen_names.add(file_path.name)
                    
                    stat = file_path.stat()
                    notes = notes_manager.get_notes_for_file(file_path.name)
                    open_notes = [n for n in notes if n.get("status") == "open"]

                    queue_files.append({
                        "filename": file_path.name,
                        "filepath": str(file_path),
                        "size_bytes": stat.st_size,
                        "size_mb": round(stat.st_size / (1024 * 1024), 2),
                        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "location_label": location_label,
                        "has_notes": len(open_notes) > 0,
                        "notes": notes,
                        "open_notes_count": len(open_notes)
                    })

    return {"files": queue_files, "total": len(queue_files)}

@app.post("/api/files/sort")
def sort_file(req: SortFileRequest, authenticated: bool = Depends(require_admin)):
    """
    Applies manual classification:
    1. Generates standardized filename with Rabbi, Topic, and Hebrew Date.
    2. Embeds ID3 tags (Artist, Title, Album) into the audio file.
    3. Moves file to final destination folder.
    4. Optionally resolves associated student note.
    5. Records action in history.
    """
    file_path = locate_audio_file(req.filename)
    if not file_path or not file_path.exists():
        raise HTTPException(status_code=404, detail="Source audio file not found")

    ext = file_path.suffix.lower()
    stat = file_path.stat()
    file_dt = datetime.fromtimestamp(stat.st_mtime)

    hebrew_date_str = req.hebrew_date or get_hebrew_date_str(file_dt)
    clean_rabbi = req.rabbi_name.strip()
    clean_topic = req.topic.strip().replace(" ", "_").replace("/", "_").replace("\\", "_")
    
    # Format: הרב_שם_נושא_תאריך.mp3
    target_filename = f"{clean_rabbi.replace(' ', '_')}_{clean_topic}_{hebrew_date_str}{ext}"

    # Determine destination directory
    if config.USE_NETWORK_SHARE and is_share_mounted():
        dest_dir = config.SMB_MOUNT_POINT / config.SMB_TARGET_SUBDIR_NAME
    else:
        dest_dir = config.SORTED_DIR

    dest_dir.mkdir(parents=True, exist_ok=True)
    unique_target_path = get_unique_filepath(dest_dir, target_filename)

    # 1. Embed ID3 tags
    metadata = {"rabbi": clean_rabbi, "topic": req.topic.strip()}
    apply_id3_tags(filepath=file_path, metadata=metadata, hebrew_date_str=hebrew_date_str)

    # 2. Move file
    final_path = safe_move(str(file_path), unique_target_path)

    # 3. Resolve note if requested
    if req.note_id_to_resolve:
        notes_manager.resolve_note(
            note_id=req.note_id_to_resolve,
            resolution_note=f"מויין ע\"י מנהל: {final_path.name}"
        )

    # 4. Record history
    record_history(
        original_filename=file_path.name,
        final_filepath=final_path,
        status="sorted_manually",
        metadata={
            "rabbi": clean_rabbi,
            "topic": req.topic.strip(),
            "hebrew_date": hebrew_date_str,
            "manual_sort": True
        }
    )

    return {
        "success": True,
        "original_filename": file_path.name,
        "new_filename": final_path.name,
        "destination": str(final_path)
    }

# ==========================================
# Static Files & Pages Routing
# ==========================================
config.STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")

@app.get("/student")
def student_page():
    """Serves the Student note submission UI."""
    student_html = config.STATIC_DIR / "student.html"
    if student_html.exists():
        return FileResponse(str(student_html))
    return HTMLResponse("<h1>Student Portal Loading...</h1>")

@app.get("/admin")
def admin_page():
    """Serves the Admin sorting and management dashboard."""
    admin_html = config.STATIC_DIR / "admin.html"
    if admin_html.exists():
        return FileResponse(str(admin_html))
    return HTMLResponse("<h1>Admin Dashboard Loading...</h1>")

@app.get("/")
def root_redirect():
    """Redirects root to /admin."""
    return RedirectResponse(url="/admin")

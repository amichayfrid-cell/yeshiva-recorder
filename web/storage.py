import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

import config

NOTES_FILE = config.DATA_DIR / "notes.json"

# In-memory folder cache (path -> (timestamp, data)) with 30-second TTL
FOLDER_CACHE: Dict[str, tuple[float, Dict[str, Any]]] = {}
CACHE_TTL_SEC = 30.0

def get_notes_data() -> List[Dict[str, Any]]:
    """Loads all student feedback notes."""
    if not NOTES_FILE.exists():
        return []
    try:
        with open(NOTES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_note(
    filename: str,
    original_path: str,
    note_type: str,
    description: str,
    student_name: Optional[str] = None
) -> Dict[str, Any]:
    """Saves a new note submitted by a student."""
    notes = get_notes_data()
    new_note = {
        "id": int(time.time() * 1000),
        "filename": os.path.basename(filename),
        "original_path": original_path,
        "note_type": note_type,
        "description": description,
        "student_name": student_name or "תלמיד אנונימי",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "open"
    }
    notes.insert(0, new_note)
    
    NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(NOTES_FILE, "w", encoding="utf-8") as f:
        json.dump(notes, f, ensure_ascii=False, indent=2)
        
    return new_note

def update_note_status(note_id: int, status: str) -> bool:
    """Updates status of a note (e.g., 'resolved')."""
    notes = get_notes_data()
    updated = False
    for n in notes:
        if n.get("id") == note_id:
            n["status"] = status
            updated = True
            break
    if updated:
        with open(NOTES_FILE, "w", encoding="utf-8") as f:
            json.dump(notes, f, ensure_ascii=False, indent=2)
    return updated

def get_notes_for_file(filename: str) -> List[Dict[str, Any]]:
    """Returns open notes matching a specific filename."""
    base = os.path.basename(filename)
    return [n for n in get_notes_data() if n.get("filename") == base and n.get("status") == "open"]

def list_direct_subfolders(target_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Blazing fast subfolder listing using os.scandir and in-memory cache.
    Ignores non-directory files entirely to eliminate network overhead.
    """
    root_str = str(config.NETWORK_MOUNT_POINT if config.NETWORK_MOUNT_POINT.exists() else config.LOCAL_STAGING_DIR)

    if not target_path or target_path == "":
        current_dir_str = root_str
    else:
        current_dir_str = os.path.abspath(target_path)
        if not current_dir_str.startswith(root_str):
            current_dir_str = root_str

    if not os.path.isdir(current_dir_str):
        current_dir_str = root_str

    # Check cache
    now = time.time()
    if current_dir_str in FOLDER_CACHE:
        cached_time, cached_data = FOLDER_CACHE[current_dir_str]
        if now - cached_time < CACHE_TTL_SEC:
            return cached_data

    subfolders = []
    ignored = {"שיעורים למיון", "incoming", "needs_review", "lost+found", "$RECYCLE.BIN", "System Volume Information"}

    try:
        with os.scandir(current_dir_str) as it:
            for entry in it:
                try:
                    if entry.is_dir(follow_symlinks=False) and not entry.name.startswith("."):
                        if entry.name not in ignored:
                            rel_path = os.path.relpath(entry.path, root_str)
                            subfolders.append({
                                "name": entry.name,
                                "rel_path": "" if rel_path == "." else rel_path,
                                "full_path": entry.path
                            })
                except OSError:
                    continue
    except (PermissionError, OSError) as e:
        print(f"[Storage] Error reading dir {current_dir_str}: {e}")

    # Sort alphabetically
    subfolders.sort(key=lambda x: x["name"])

    # Calculate rel path
    rel_from_root = os.path.relpath(current_dir_str, root_str)
    current_rel = "" if rel_from_root == "." else rel_from_root
    current_name = "ראשי (שרת הישיבה)" if current_dir_str == root_str else os.path.basename(current_dir_str)
    
    parent_dir = os.path.dirname(current_dir_str)
    parent_path = parent_dir if (current_dir_str != root_str and parent_dir.startswith(root_str)) else None

    result = {
        "current_full_path": current_dir_str,
        "current_rel_path": current_rel,
        "current_name": current_name,
        "parent_path": parent_path,
        "is_root": current_dir_str == root_str,
        "subfolders": subfolders
    }

    # Store in cache
    FOLDER_CACHE[current_dir_str] = (now, result)
    return result

def create_new_folder(base_folder: str, new_folder_name: str) -> str:
    """
    Creates a new folder inside base_folder and clears cache.
    """
    clean_name = new_folder_name.strip().replace("/", "").replace("\\", "")
    if not clean_name:
        raise ValueError("שם התיקייה אינו יכול להיות ריק")
        
    target = os.path.join(base_folder, clean_name)
    os.makedirs(target, exist_ok=True)
    
    # Invalidate cache for base folder
    FOLDER_CACHE.pop(base_folder, None)
    return target

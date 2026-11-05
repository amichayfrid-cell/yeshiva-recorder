import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

import config
from core.hebrew_date import get_hebrew_date_str

NOTES_FILE = config.DATA_DIR / "notes.json"

# In-memory folder cache (path -> (timestamp, data)) with 30-second TTL
FOLDER_CACHE: Dict[str, tuple[float, Dict[str, Any]]] = {}
CACHE_TTL_SEC = 30.0

def get_notes_data() -> List[Dict[str, Any]]:
    """Loads all student feedback notes and auto-deletes notes older than 30 days."""
    if not NOTES_FILE.exists():
        return []
    try:
        with open(NOTES_FILE, "r", encoding="utf-8") as f:
            notes = json.load(f)
        
        now = datetime.now()
        valid_notes = []
        modified = False
        for n in notes:
            created_str = n.get("created_at")
            if created_str:
                try:
                    dt = datetime.strptime(created_str, "%Y-%m-%d %H:%M:%S")
                    if (now - dt).days >= 30:
                        modified = True
                        continue
                    if not n.get("hebrew_date"):
                        n["hebrew_date"] = get_hebrew_date_str(dt)
                        modified = True
                    if not n.get("created_time"):
                        n["created_time"] = dt.strftime("%H:%M")
                        modified = True
                except Exception:
                    pass
            if not n.get("hebrew_date"):
                n["hebrew_date"] = get_hebrew_date_str(now)
                modified = True
            if not n.get("created_time"):
                n["created_time"] = now.strftime("%H:%M")
                modified = True
            valid_notes.append(n)
            
        if modified:
            try:
                with open(NOTES_FILE, "w", encoding="utf-8") as f:
                    json.dump(valid_notes, f, ensure_ascii=False, indent=2)
            except Exception:
                pass
                
        return valid_notes
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
    now_dt = datetime.now()
    hebrew_date = get_hebrew_date_str(now_dt)
    new_note = {
        "id": int(time.time() * 1000),
        "filename": os.path.basename(filename),
        "original_path": original_path,
        "note_type": note_type,
        "description": description,
        "student_name": student_name or "תלמיד אנונימי",
        "created_at": now_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "created_time": now_dt.strftime("%H:%M"),
        "hebrew_date": hebrew_date,
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
    base = os.path.basename(filename.replace('\\', '/'))
    return [n for n in get_notes_data() if os.path.basename(n.get("filename", "").replace('\\', '/')) == base and n.get("status") == "open"]

def list_direct_subfolders(target_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Blazing fast subfolder listing using os.scandir and in-memory cache.
    Ignores non-directory files entirely to eliminate network overhead.
    """
    root_str = str(config.NETWORK_MOUNT_POINT if config.is_network_share_mounted() else config.LOCAL_STAGING_DIR)

    if not target_path or target_path == "":
        current_dir_str = root_str
    else:
        clean_target = str(target_path).replace("\\", "/").strip()
        if os.path.isabs(clean_target) and clean_target.startswith(root_str):
            current_dir_str = os.path.abspath(clean_target)
        else:
            rel_candidate = os.path.abspath(os.path.join(root_str, clean_target.lstrip("/")))
            if rel_candidate.startswith(root_str) and os.path.isdir(rel_candidate):
                current_dir_str = rel_candidate
            elif os.path.isabs(clean_target) and os.path.isdir(clean_target):
                current_dir_str = os.path.abspath(clean_target)
            else:
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
    audio_files = []
    ignored = {"שיעורים למיון", "incoming", "needs_review", "lost+found", "$RECYCLE.BIN", "System Volume Information"}

    try:
        with os.scandir(current_dir_str) as it:
            for entry in it:
                try:
                    if entry.name.startswith("."):
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name not in ignored and "הגברת החירות" not in entry.name:
                            rel_path = os.path.relpath(entry.path, root_str)
                            subfolders.append({
                                "name": entry.name,
                                "rel_path": "" if rel_path == "." else rel_path,
                                "full_path": entry.path
                            })
                    elif entry.is_file(follow_symlinks=False):
                        ext = os.path.splitext(entry.name)[1].lower()
                        if ext in [".mp3", ".wav", ".m4a", ".ogg"]:
                            audio_files.append(entry.name)
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
        "subfolders": subfolders,
        "audio_files": sorted(audio_files),
        "root_full_path": root_str
    }

    # Store in cache
    FOLDER_CACHE[current_dir_str] = (now, result)
    return result

_ALL_FOLDERS_CACHE = None
_ALL_FOLDERS_CACHE_TIME = 0.0
ALL_FOLDERS_CACHE_TTL = 180.0  # 3 minutes

def get_all_folders_flat() -> List[Dict[str, Any]]:
    """
    Crawls the root folder and builds a flat list of all navigable directories.
    Cached in memory for high-speed search without repeated disk/SMB hits.
    """
    global _ALL_FOLDERS_CACHE, _ALL_FOLDERS_CACHE_TIME
    now = time.time()
    if _ALL_FOLDERS_CACHE is not None and (now - _ALL_FOLDERS_CACHE_TIME) < ALL_FOLDERS_CACHE_TTL:
        return _ALL_FOLDERS_CACHE

    root_str = str(config.NETWORK_MOUNT_POINT if config.is_network_share_mounted() else config.LOCAL_STAGING_DIR)
    if not os.path.isdir(root_str):
        return []

    ignored = {"שיעורים למיון", "incoming", "needs_review", "lost+found", "$RECYCLE.BIN", "System Volume Information"}
    folders = []

    try:
        for root, dirs, _ in os.walk(root_str):
            # In-place filtering of ignored and hidden directories
            dirs[:] = [
                d for d in dirs 
                if not d.startswith(".") 
                and d not in ignored 
                and "הגברת החירות" not in d
            ]
            
            for d in dirs:
                full_d = os.path.join(root, d)
                rel_d = os.path.relpath(full_d, root_str).replace("\\", "/")
                parts = [p for p in rel_d.split("/") if p]
                breadcrumb = " ❯ ".join(parts)
                folders.append({
                    "name": d,
                    "rel_path": rel_d,
                    "full_path": full_d,
                    "breadcrumb": breadcrumb
                })
    except Exception as e:
        print(f"[Storage] Error crawling all folders: {e}")

    _ALL_FOLDERS_CACHE = folders
    _ALL_FOLDERS_CACHE_TIME = now
    return folders

def search_folders(query: str, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Searches for folders matching the given query (case-insensitive Hebrew/English).
    Prioritizes matches in folder name over path matches.
    """
    clean_q = query.strip().lower()
    if not clean_q:
        return []

    all_folders = get_all_folders_flat()
    name_matches = []
    path_matches = []

    for f in all_folders:
        fn_lower = f["name"].lower()
        rel_lower = f["rel_path"].lower()
        if clean_q in fn_lower:
            name_matches.append(f)
        elif clean_q in rel_lower:
            path_matches.append(f)

    # Sort name matches: exact match first, then shorter name, then alphabetical
    name_matches.sort(key=lambda x: (x["name"].lower() != clean_q, len(x["name"]), x["name"]))
    path_matches.sort(key=lambda x: (len(x["rel_path"]), x["rel_path"]))

    results = (name_matches + path_matches)[:limit]
    return results

def create_new_folder(base_folder: str, new_folder_name: str) -> str:
    """
    Creates a new folder inside base_folder and clears cache.
    """
    clean_name = new_folder_name.strip().replace("/", "").replace("\\", "")
    if not clean_name:
        raise ValueError("שם התיקייה אינו יכול להיות ריק")
        
    target = os.path.join(base_folder, clean_name)
    os.makedirs(target, exist_ok=True)
    
    # Invalidate cache for base folder and global search cache
    FOLDER_CACHE.pop(base_folder, None)
    global _ALL_FOLDERS_CACHE
    _ALL_FOLDERS_CACHE = None
    return target

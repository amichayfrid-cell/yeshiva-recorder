import re
import json
import os
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

import config
from core.hebrew_date import get_hebrew_date_str

NOTES_FILE = config.DATA_DIR / "notes.json"

RECORDER_SOURCES_FILE = config.DATA_DIR / "recorder_sources.json"
_RECORDER_SOURCES_CACHE: Optional[Dict[str, str]] = None
_RECORDER_NEGATIVE_CACHE: set = set()

def decode_raw_label(raw_label: Optional[str]) -> str:
    """
    Decodes raw drive labels that might contain hex escapes (e.g. '\\x8e\\x97\\x8c\\x88 4'),
    octal escapes, CP862 (Hebrew DOS OEM) bytes, CP1255, or Latin-1 artifacts.
    """
    if not raw_label:
        return ""
    s = str(raw_label).strip()

    # 1. Handle hex escapes like \x8e\x97\x8c\x88 or \x8e\x97\x8c\x88\ 4
    if r'\x' in s or r'\X' in s:
        try:
            def rep_hex(m):
                hex_str = m.group(0)
                byte_vals = bytes.fromhex(re.sub(r'\\[xX]', '', hex_str))
                for enc in ('cp862', 'cp1255', 'utf-8'):
                    try:
                        return byte_vals.decode(enc)
                    except Exception:
                        pass
                return hex_str
            s = re.sub(r'(?:\\[xX][0-9a-fA-F]{2})+', rep_hex, s)
        except Exception:
            pass

    # 2. Handle octal escapes like \216\227\214\210 (common in blkid / lsblk)
    if re.search(r'\\[0-3][0-7]{2}', s):
        try:
            def rep_oct(m):
                oct_str = m.group(0).replace('\\', '')
                byte_val = bytes([int(oct_str, 8)])
                for enc in ('cp862', 'cp1255', 'utf-8'):
                    try:
                        return byte_val.decode(enc)
                    except Exception:
                        pass
                return m.group(0)
            s = re.sub(r'(?:\\[0-3][0-7]{2})+', rep_oct, s)
        except Exception:
            pass

    # 3. Handle high-byte characters (ord >= 0x80) misread as Latin-1
    if any(0x80 <= ord(c) <= 0xFF for c in s):
        try:
            raw_bytes = s.encode('latin1')
            for enc in ('cp862', 'cp1255', 'utf-8'):
                try:
                    decoded = raw_bytes.decode(enc)
                    if any('֐' <= c <= '׿' for c in decoded):
                        s = decoded
                        break
                except Exception:
                    pass
        except Exception:
            pass

    # Clean escaped spaces or backslashes like '\ 4' or '4\'
    s = s.replace('\\', ' ')
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def normalize_recorder_label(raw_label: Optional[str]) -> Optional[str]:
    """
    Cleans and normalizes various recorder naming conventions into a clean Hebrew label.
    Decodes CP862/hex escapes automatically.
    Examples:
    - '\\x8e\\x97\\x8c\\x88 4' -> 'מקלט 4'
    - 'מקלט 4', 'מקלט_4', 'מקלט-4', 'מקלט4' -> 'מקלט 4'
    - 'RECORDER 4', 'RECORDER_4', 'REC-4', 'REC4' -> 'מקלט 4'
    - 'MIKLET 4', 'MEKALET 4', 'MIKLET_4' -> 'מקלט 4'
    - 'DOK 4', 'USB 4', 'USB4' -> 'מקלט 4'
    - '4', '04' -> 'מקלט 4'
    - 'מקלט ראשי', 'ספרייה', 'בית מדרש' -> 'מקלט בית מדרש' / keep custom
    """
    if not raw_label:
        return None
    clean = decode_raw_label(raw_label)
    if not clean:
        return None
    generic = {
        'NO NAME', 'NONAME', 'UNTITLED', 'USB DISK', 'USB DRIVE', 'REMOVABLE',
        'TRANSCEND', 'SANDISK', 'KINGSTON', 'FAT32', 'FAT16', 'EXFAT', 'VOLUME',
        'NEW VOLUME', 'LOCAL DISK', 'DISK', 'USB', 'SD', 'DRIVE'
    }
    if clean.upper() in generic:
        return None

    # Filter out single English drive letters (e.g. 'O', 'D', 'E', 'F') or 'מקלט O' (Windows drive letter artifact)
    if len(clean) == 1 and clean.isalpha() and clean.isascii():
        return None
    if re.fullmatch(r'מקלט\s+[a-zA-Z]', clean, re.IGNORECASE):
        return None

    # Check Hebrew pattern: 'מקלט X'
    m_heb = re.search(r'מקלט[\s_-]*([0-9א-ת]+|[a-zA-Z]+)?', clean)
    if m_heb:
        suffix = m_heb.group(1)
        if suffix:
            return f"מקלט {suffix.strip()}"
        return clean

    # Check English pattern: 'RECORDER X', 'REC X', 'MIKLET X'
    m_eng = re.search(r'(?:RECORDER|MIKLET|MEKALET|REC|DOK|USB)[\s_-]*([0-9]+|[a-zA-Z]|א-ת)', clean, re.IGNORECASE)
    if m_eng:
        val = m_eng.group(1).strip()
        return f"מקלט {val}"

    # Pure number e.g. '4' or '04'
    m_num = re.fullmatch(r'0*([1-9][0-9]*)', clean)
    if m_num:
        return f"מקלט {m_num.group(1)}"

    # Hebrew words
    if any('֐' <= c <= '׿' for c in clean):
        if not clean.startswith('מקלט'):
            return f"מקלט {clean}"
        return clean

    return clean

def get_recorder_sources() -> Dict[str, str]:
    global _RECORDER_SOURCES_CACHE
    if _RECORDER_SOURCES_CACHE is not None:
        return dict(_RECORDER_SOURCES_CACHE)
    if not RECORDER_SOURCES_FILE.exists():
        _RECORDER_SOURCES_CACHE = {}
        return {}
    try:
        with open(RECORDER_SOURCES_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
            cleaned = {}
            modified = False
            for k, v in raw.items():
                norm = normalize_recorder_label(v) or v
                cleaned[k] = norm
                if norm != v:
                    modified = True
            _RECORDER_SOURCES_CACHE = cleaned
            if modified:
                try:
                    with open(RECORDER_SOURCES_FILE, "w", encoding="utf-8") as fw:
                        json.dump(cleaned, fw, ensure_ascii=False, indent=2)
                except Exception:
                    pass
            return dict(_RECORDER_SOURCES_CACHE)
    except Exception:
        _RECORDER_SOURCES_CACHE = {}
        return {}

def get_recorder_source(filename: str, filepath: Optional[Path] = None) -> Optional[str]:
    sources = get_recorder_sources()
    clean_fn = os.path.basename(filename.replace('\\', '/'))
    if clean_fn in sources:
        return normalize_recorder_label(sources[clean_fn]) or sources[clean_fn]

    # Check base filename without duplicate suffix e.g. '_1.mp3', '_2.mp3'
    base_match = re.sub(r'_\d+\.mp3$', '.mp3', clean_fn, flags=re.IGNORECASE)
    if base_match != clean_fn and base_match in sources:
        return normalize_recorder_label(sources[base_match]) or sources[base_match]

    # Try reading from ID3 tag if filepath exists (cached to avoid repeat network reads)
    if clean_fn not in _RECORDER_NEGATIVE_CACHE and filepath and filepath.exists() and filepath.suffix.lower() == ".mp3":
        try:
            from mutagen.id3 import ID3
            audio = ID3(str(filepath))
            for frame in audio.getall("TXXX"):
                if frame.desc.lower() in ("recorder", "recorder_name", "מקלט"):
                    val = str(frame.text[0]).strip()
                    if val:
                        norm = normalize_recorder_label(val) or val
                        set_recorder_source(clean_fn, norm)
                        return norm
            _RECORDER_NEGATIVE_CACHE.add(clean_fn)
        except Exception:
            _RECORDER_NEGATIVE_CACHE.add(clean_fn)

    return None

def set_recorder_source(filename: str, source_label: str):
    global _RECORDER_SOURCES_CACHE
    sources = get_recorder_sources()
    clean_fn = os.path.basename(filename.replace('\\', '/'))
    clean_lbl = normalize_recorder_label(source_label) or source_label.strip()
    sources[clean_fn] = clean_lbl
    _RECORDER_SOURCES_CACHE = sources
    try:
        RECORDER_SOURCES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(RECORDER_SOURCES_FILE, "w", encoding="utf-8") as f:
            json.dump(sources, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def set_all_recorders_source(old_label: str, new_label: str):
    global _RECORDER_SOURCES_CACHE
    sources = get_recorder_sources()
    norm_old = normalize_recorder_label(old_label) or old_label.strip()
    norm_new = normalize_recorder_label(new_label) or new_label.strip()
    updated = False
    for fn, lbl in list(sources.items()):
        if lbl == norm_old or lbl == old_label:
            sources[fn] = norm_new
            updated = True
    if updated:
        _RECORDER_SOURCES_CACHE = sources
        try:
            RECORDER_SOURCES_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(RECORDER_SOURCES_FILE, "w", encoding="utf-8") as f:
                json.dump(sources, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

def remove_recorder_source(filename: str):
    global _RECORDER_SOURCES_CACHE
    sources = get_recorder_sources()
    clean_fn = os.path.basename(filename.replace('\\', '/'))
    if clean_fn in sources:
        sources.pop(clean_fn, None)
        _RECORDER_SOURCES_CACHE = sources
        try:
            with open(RECORDER_SOURCES_FILE, "w", encoding="utf-8") as f:
                json.dump(sources, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


# In-memory notes cache with mtime and TTL validation
_NOTES_CACHE: Optional[List[Dict[str, Any]]] = None
_NOTES_CACHE_MTIME: float = 0.0
_NOTES_CACHE_TIME: float = 0.0
_NOTES_CACHE_TTL: float = 15.0

def invalidate_notes_cache():
    global _NOTES_CACHE
    _NOTES_CACHE = None


# In-memory folder cache (path -> (timestamp, data)) with 30-second TTL
FOLDER_CACHE: Dict[str, tuple[float, Dict[str, Any]]] = {}
CACHE_TTL_SEC = 30.0

def get_notes_data() -> List[Dict[str, Any]]:
    """Loads all student feedback notes with in-memory caching and auto-deletes notes older than 30 days."""
    global _NOTES_CACHE, _NOTES_CACHE_MTIME, _NOTES_CACHE_TIME
    now_ts = time.time()
    if not NOTES_FILE.exists():
        _NOTES_CACHE = []
        return []

    try:
        current_mtime = NOTES_FILE.stat().st_mtime
        if _NOTES_CACHE is not None and (now_ts - _NOTES_CACHE_TIME < _NOTES_CACHE_TTL) and current_mtime == _NOTES_CACHE_MTIME:
            return [dict(n) for n in _NOTES_CACHE]
    except OSError:
        pass

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

        try:
            _NOTES_CACHE_MTIME = NOTES_FILE.stat().st_mtime
        except OSError:
            _NOTES_CACHE_MTIME = now_ts
        _NOTES_CACHE_TIME = now_ts
        _NOTES_CACHE = valid_notes
        return [dict(n) for n in valid_notes]
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
    
    invalidate_notes_cache()
    NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(NOTES_FILE, "w", encoding="utf-8") as f:
        json.dump(notes, f, ensure_ascii=False, indent=2)
        
    return new_note

def update_note_status(note_id: Any, status: str) -> bool:
    """Updates status of a note (e.g., 'resolved'). Accepts either int or str ID."""
    notes = get_notes_data()
    updated = False
    str_id = str(note_id).strip() if note_id is not None else ""
    for n in notes:
        if str(n.get("id")) == str_id:
            n["status"] = status
            updated = True
            break
    if updated:
        invalidate_notes_cache()
        with open(NOTES_FILE, "w", encoding="utf-8") as f:
            json.dump(notes, f, ensure_ascii=False, indent=2)
    return updated

def get_notes_for_file(filename: str) -> List[Dict[str, Any]]:
    """Returns open notes matching a specific filename."""
    base = os.path.basename(filename.replace('\\', '/'))
    return [n for n in get_notes_data() if os.path.basename(n.get("filename", "").replace('\\', '/')) == base and n.get("status") == "open"]

FOLDERS_CACHE_FILE = config.DATA_DIR / "folders_tree_cache.json"

IGNORED_FOLDER_EXACT = {
    "שיעורים למיון", 
    "incoming", 
    "needs_review", 
    "lost+found", 
    "$recycle.bin", 
    "system volume information"
}

def is_ignored_folder_name(name: str) -> bool:
    if not name:
        return True
    clean = str(name).strip()
    if clean.startswith("."):
        return True
    if clean.lower() in IGNORED_FOLDER_EXACT:
        return True
    if "הגברת החירות" in clean:
        return True
    if "אחראי שמע" in clean:
        return True
    if "ארכיון" in clean:
        return True
    return False

def is_ignored_folder_path(rel_path: str) -> bool:
    if not rel_path:
        return False
    parts = [p.strip() for p in str(rel_path).replace("\\", "/").split("/") if p.strip()]
    return any(is_ignored_folder_name(p) for p in parts)

def get_explorer_root() -> Path:
    """
    Returns the root directory for exploring and searching folders.
    Always uses NETWORK_MOUNT_POINT (/mnt/yeshiva_share) if accessible,
    falling back to get_final_target_dir() or LOCAL_STAGING_DIR.
    """
    if config.NETWORK_MOUNT_POINT.exists() and config.NETWORK_MOUNT_POINT.is_dir():
        try:
            with os.scandir(str(config.NETWORK_MOUNT_POINT)) as it:
                for entry in it:
                    if not entry.name.startswith("."):
                        return config.NETWORK_MOUNT_POINT
        except Exception:
            pass
            
    try:
        target = config.get_final_target_dir()
        if target.exists() and target.is_dir():
            return target
    except Exception:
        pass

    return config.LOCAL_STAGING_DIR

def list_direct_subfolders(target_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Blazing fast subfolder listing using os.scandir and in-memory cache.
    Ignores non-directory files entirely to eliminate network overhead.
    """
    root_path = get_explorer_root()
    root_str = str(root_path)

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

    try:
        with os.scandir(current_dir_str) as it:
            for entry in it:
                try:
                    if entry.name.startswith("."):
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        if not is_ignored_folder_name(entry.name):
                            rel_path = os.path.relpath(entry.path, root_str)
                            if not is_ignored_folder_path(rel_path):
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
_IS_CRAWLING_FOLDERS = False
ALL_FOLDERS_CACHE_TTL = 300.0  # 5 minutes

def _crawl_all_folders_worker():
    global _ALL_FOLDERS_CACHE, _ALL_FOLDERS_CACHE_TIME, _IS_CRAWLING_FOLDERS
    try:
        root_path = get_explorer_root()
        root_str = str(root_path)
        if not os.path.isdir(root_str):
            return

        folders = []

        # Recursively traverse all subfolders across all directory levels
        for root, dirs, _ in os.walk(root_str, followlinks=False):
            dirs[:] = [
                d for d in dirs 
                if not is_ignored_folder_name(d)
            ]
            
            for d in dirs:
                full_d = os.path.join(root, d)
                try:
                    rel_d = os.path.relpath(full_d, root_str).replace("\\", "/")
                    if is_ignored_folder_path(rel_d):
                        continue
                    parts = [p for p in rel_d.split("/") if p]
                    breadcrumb = " ❯ ".join(parts)
                    folders.append({
                        "name": d,
                        "rel_path": rel_d,
                        "full_path": full_d,
                        "breadcrumb": breadcrumb
                    })
                except Exception:
                    pass

        # Only update cache if folders were discovered
        if folders:
            _ALL_FOLDERS_CACHE = folders
            _ALL_FOLDERS_CACHE_TIME = time.time()
            try:
                FOLDERS_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
                with open(FOLDERS_CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump(folders, f, ensure_ascii=False)
            except Exception as save_err:
                print(f"[Storage] Could not persist folders tree cache: {save_err}")
    except Exception as e:
        print(f"[Storage] Error during folder crawl: {e}")
    finally:
        _IS_CRAWLING_FOLDERS = False

def get_all_folders_flat() -> List[Dict[str, Any]]:
    """
    Crawls the root folder and builds a flat list of all navigable directories and sub-directories.
    Uses memory cache + persistent disk cache to guarantee instant search across thousands of subfolders.
    """
    global _ALL_FOLDERS_CACHE, _ALL_FOLDERS_CACHE_TIME, _IS_CRAWLING_FOLDERS
    now = time.time()

    # 1. In-memory cache hit if populated
    if _ALL_FOLDERS_CACHE and len(_ALL_FOLDERS_CACHE) > 0:
        if (now - _ALL_FOLDERS_CACHE_TIME) > ALL_FOLDERS_CACHE_TTL and not _IS_CRAWLING_FOLDERS:
            _IS_CRAWLING_FOLDERS = True
            threading.Thread(target=_crawl_all_folders_worker, daemon=True).start()
        return _ALL_FOLDERS_CACHE

    # 2. Persistent disk cache hit
    if FOLDERS_CACHE_FILE.exists():
        try:
            with open(FOLDERS_CACHE_FILE, "r", encoding="utf-8") as f:
                disk_folders = json.load(f)
                if disk_folders and len(disk_folders) > 0:
                    disk_folders = [
                        f for f in disk_folders 
                        if not is_ignored_folder_name(f.get("name", "")) 
                        and not is_ignored_folder_path(f.get("rel_path", ""))
                    ]
                    _ALL_FOLDERS_CACHE = disk_folders
                    _ALL_FOLDERS_CACHE_TIME = FOLDERS_CACHE_FILE.stat().st_mtime
                    if (now - _ALL_FOLDERS_CACHE_TIME) > ALL_FOLDERS_CACHE_TTL and not _IS_CRAWLING_FOLDERS:
                        _IS_CRAWLING_FOLDERS = True
                        threading.Thread(target=_crawl_all_folders_worker, daemon=True).start()
                    return _ALL_FOLDERS_CACHE
        except Exception:
            pass

    # 3. Synchronous crawl if cache is empty
    _IS_CRAWLING_FOLDERS = True
    _crawl_all_folders_worker()
    return _ALL_FOLDERS_CACHE or []

# Pre-warm folder cache in background on module startup
threading.Thread(target=_crawl_all_folders_worker, daemon=True).start()

def search_folders(query: str, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Searches for folders and subfolders matching the given query across all directory depths.
    Supports multi-word queries (e.g. 'הרב אורי', 'עיון בבא מציעא', 'תשפד').
    Prioritizes exact subfolder name matches, then subfolder prefix, then path breadcrumb matches.
    """
    clean_q = query.strip().lower()
    if not clean_q:
        return []

    words = [w for w in clean_q.split() if w]
    all_folders = get_all_folders_flat()

    exact_name = []
    starts_with_name = []
    contains_name = []
    path_matches = []

    for f in all_folders:
        if is_ignored_folder_name(f.get("name", "")) or is_ignored_folder_path(f.get("rel_path", "")):
            continue

        fn_lower = f["name"].lower()
        rel_lower = f["rel_path"].lower()

        # Check if all query words appear in the name or the full relative path
        if not all(w in rel_lower for w in words):
            continue

        if fn_lower == clean_q:
            exact_name.append(f)
        elif fn_lower.startswith(clean_q):
            starts_with_name.append(f)
        elif all(w in fn_lower for w in words):
            contains_name.append(f)
        else:
            path_matches.append(f)

    # Sort results
    exact_name.sort(key=lambda x: len(x["rel_path"]))
    starts_with_name.sort(key=lambda x: (len(x["name"]), x["name"]))
    contains_name.sort(key=lambda x: (len(x["name"]), x["name"]))
    path_matches.sort(key=lambda x: (len(x["rel_path"]), x["rel_path"]))

    results = (exact_name + starts_with_name + contains_name + path_matches)[:limit]
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

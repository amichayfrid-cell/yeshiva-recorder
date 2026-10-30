import time
from pathlib import Path
from typing import Optional

# Base Paths (Local Server Storage)
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

INCOMING_DIR = DATA_DIR / "incoming"
LOCAL_STAGING_DIR = DATA_DIR / "needs_review"  # Local storage buffer (Stage 1)
RAV_TZVI_DIR = DATA_DIR / "rav_tzvi"
NOAM_DIR = DATA_DIR / "noam"
STATIC_DIR = BASE_DIR / "web" / "static"
HISTORY_FILE = DATA_DIR / "history.json"
MAX_HISTORY_ENTRIES = 500  # Maximum records in history

# Yeshiva Central File Server (SMB Share - Stage 2)
NETWORK_MOUNT_POINT = Path("/mnt/yeshiva_share")
NETWORK_TARGET_DIR = NETWORK_MOUNT_POINT / "שיעורי השבוע"

# Upload Directory (\\mdserver\העלאת שיעורים)
NETWORK_UPLOAD_MOUNT = Path("/mnt/yeshiva_upload")
NETWORK_SHARE_UPLOAD_SUBDIR = NETWORK_MOUNT_POINT / "העלאת שיעורים"
LOCAL_UPLOAD_DIR = DATA_DIR / "upload_lessons"

_MOUNT_CACHE = None
_MOUNT_CACHE_TIME = 0.0

def is_path_mounted(path: Path) -> bool:
    """Checks if a given path is an actual mounted filesystem (from /proc/mounts)."""
    proc_mounts = Path("/proc/mounts")
    if proc_mounts.exists():
        try:
            target = str(path)
            for line in proc_mounts.read_text(errors="ignore").splitlines():
                parts = line.split()
                if len(parts) >= 2 and parts[1].replace("\\040", " ") == target:
                    return True
            return False
        except Exception:
            pass
    try:
        return path.is_mount()
    except Exception:
        return False

def _is_real_mount() -> bool:
    """True if NETWORK_MOUNT_POINT is an actual mounted filesystem (not just a local folder)."""
    return is_path_mounted(NETWORK_MOUNT_POINT)

def is_network_share_mounted() -> bool:
    """Checks if NETWORK_MOUNT_POINT is really mounted and readable (cached for 15s)."""
    global _MOUNT_CACHE, _MOUNT_CACHE_TIME
    now = time.time()
    if _MOUNT_CACHE is not None and (now - _MOUNT_CACHE_TIME) < 15.0:
        return _MOUNT_CACHE

    if not NETWORK_MOUNT_POINT.exists() or not NETWORK_MOUNT_POINT.is_dir():
        _MOUNT_CACHE = False
        _MOUNT_CACHE_TIME = now
        return False
    try:
        res = _is_real_mount() and any(item for item in NETWORK_MOUNT_POINT.iterdir() if not item.name.startswith("."))
        _MOUNT_CACHE = res
        _MOUNT_CACHE_TIME = now
        return res
    except Exception:
        _MOUNT_CACHE = False
        _MOUNT_CACHE_TIME = now
        return False

# Target Directory Resolver (uses Network if mounted, falls back to Local Staging)
def get_final_target_dir() -> Path:
    if is_network_share_mounted() and NETWORK_TARGET_DIR.exists() and NETWORK_TARGET_DIR.is_dir():
        return NETWORK_TARGET_DIR
    return LOCAL_STAGING_DIR

def get_upload_dirs() -> list[Path]:
    """Returns all available directories containing uploaded lessons."""
    candidates: list[Path] = []
    
    # 1. Dedicated CIFS mount (/mnt/yeshiva_upload)
    if NETWORK_UPLOAD_MOUNT.exists():
        is_mounted = is_path_mounted(NETWORK_UPLOAD_MOUNT)
        if not is_mounted:
            # Try on-demand mount via fstab/subproc
            try:
                import subprocess
                subprocess.run(["mount", str(NETWORK_UPLOAD_MOUNT)], capture_output=True, timeout=2)
                is_mounted = is_path_mounted(NETWORK_UPLOAD_MOUNT)
            except Exception:
                pass
                
        has_audio = False
        try:
            for item in NETWORK_UPLOAD_MOUNT.iterdir():
                if not item.name.startswith(".") and (item.is_dir() or item.suffix.lower() in USB_AUDIO_EXTENSIONS):
                    has_audio = True
                    break
        except Exception:
            pass
            
        if is_mounted or has_audio:
            candidates.append(NETWORK_UPLOAD_MOUNT)

    # 2. Subdirectory inside primary share (/mnt/yeshiva_share/העלאת שיעורים)
    if is_network_share_mounted() and NETWORK_SHARE_UPLOAD_SUBDIR.exists() and NETWORK_SHARE_UPLOAD_SUBDIR.is_dir():
        if NETWORK_SHARE_UPLOAD_SUBDIR not in candidates:
            candidates.append(NETWORK_SHARE_UPLOAD_SUBDIR)

    # 3. Any directory named 'העלאת שיעורים' inside NETWORK_MOUNT_POINT
    if is_network_share_mounted():
        try:
            for item in NETWORK_MOUNT_POINT.iterdir():
                if item.is_dir() and "העלאת שיעורים" in item.name:
                    if item not in candidates:
                        candidates.append(item)
        except Exception:
            pass

    # 4. Local fallback directory
    if LOCAL_UPLOAD_DIR.exists() and LOCAL_UPLOAD_DIR.is_dir():
        if not candidates:
            candidates.append(LOCAL_UPLOAD_DIR)

    return candidates

def get_upload_dir() -> Optional[Path]:
    """Returns the primary upload directory if available."""
    dirs = get_upload_dirs()
    return dirs[0] if dirs else None

# USB Ingestion & Media Support Configuration
USB_DELETE_AFTER_INGEST = True  # Automatically wipe recorder ONLY after verified copy
USB_POLL_INTERVAL_SEC = 2.0
USB_AUDIO_EXTENSIONS = {
    ".mp3", ".wav", ".m4a", ".aac", ".ogg", ".wma", 
    ".flac", ".opus", ".mp2", ".m4b", ".amr", ".aiff", ".aif", ".weba"
}
SUPPORTED_VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".webm", ".avi", ".mov", 
    ".wmv", ".flv", ".m4v", ".3gp", ".mpg", ".mpeg", ".ts", ".asf", ".vob", ".ogv"
}
SUPPORTED_DOCUMENT_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".txt", ".ppt", ".pptx", ".odt", ".rtf", ".xls", ".xlsx"
}
SUPPORTED_IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff", ".heic", ".svg"
}
SUPPORTED_MEDIA_EXTENSIONS = (
    USB_AUDIO_EXTENSIONS | SUPPORTED_VIDEO_EXTENSIONS | SUPPORTED_DOCUMENT_EXTENSIONS | SUPPORTED_IMAGE_EXTENSIONS
)

def ensure_directories():
    """Ensures that local directories exist."""
    for directory in [INCOMING_DIR, LOCAL_STAGING_DIR, LOCAL_UPLOAD_DIR]:
        directory.mkdir(parents=True, exist_ok=True)

# Automatically ensure directories on import
ensure_directories()

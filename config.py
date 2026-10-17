import time
from pathlib import Path

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
NETWORK_TARGET_DIR = NETWORK_MOUNT_POINT / "שיעורים למיון"

_MOUNT_CACHE = None
_MOUNT_CACHE_TIME = 0.0

def _is_real_mount() -> bool:
    """True if NETWORK_MOUNT_POINT is an actual mounted filesystem (not just a local folder)."""
    proc_mounts = Path("/proc/mounts")
    if proc_mounts.exists():
        try:
            target = str(NETWORK_MOUNT_POINT)
            for line in proc_mounts.read_text(errors="ignore").splitlines():
                parts = line.split()
                if len(parts) >= 2 and parts[1].replace("\\040", " ") == target:
                    return True
            return False
        except Exception:
            pass
    try:
        return NETWORK_MOUNT_POINT.is_mount()
    except Exception:
        return True

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
    ".pdf", ".doc", ".docx", ".txt", ".ppt", ".pptx", ".odt"
}
SUPPORTED_MEDIA_EXTENSIONS = USB_AUDIO_EXTENSIONS | SUPPORTED_VIDEO_EXTENSIONS | SUPPORTED_DOCUMENT_EXTENSIONS

def ensure_directories():
    """Ensures that local directories exist."""
    for directory in [INCOMING_DIR, LOCAL_STAGING_DIR]:
        directory.mkdir(parents=True, exist_ok=True)

# Automatically ensure directories on import
ensure_directories()

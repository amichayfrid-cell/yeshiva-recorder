from pathlib import Path

# Base Paths (Local Server Storage)
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

INCOMING_DIR = DATA_DIR / "incoming"
LOCAL_STAGING_DIR = DATA_DIR / "needs_review"  # Local storage buffer (Stage 1)
RAV_TZVI_DIR = DATA_DIR / "rav_tzvi"
STATIC_DIR = BASE_DIR / "web" / "static"
HISTORY_FILE = DATA_DIR / "history.json"
MAX_HISTORY_ENTRIES = 500  # Maximum records in history

# Yeshiva Central File Server (SMB Share - Stage 2)
NETWORK_MOUNT_POINT = Path("/mnt/yeshiva_share")
NETWORK_TARGET_DIR = NETWORK_MOUNT_POINT / "שיעורים למיון"

def is_network_share_mounted() -> bool:
    """Checks if NETWORK_MOUNT_POINT exists and actually contains files/folders (not an unmounted empty dir)."""
    if not NETWORK_MOUNT_POINT.exists() or not NETWORK_MOUNT_POINT.is_dir():
        return False
    try:
        return any(item for item in NETWORK_MOUNT_POINT.iterdir() if not item.name.startswith("."))
    except Exception:
        return False

# Target Directory Resolver (uses Network if mounted, falls back to Local Staging)
def get_final_target_dir() -> Path:
    if is_network_share_mounted() and NETWORK_TARGET_DIR.exists() and NETWORK_TARGET_DIR.is_dir():
        return NETWORK_TARGET_DIR
    return LOCAL_STAGING_DIR

# USB Ingestion Configuration
USB_DELETE_AFTER_INGEST = True  # Automatically wipe recorder ONLY after verified copy
USB_POLL_INTERVAL_SEC = 2.0
USB_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".wma"}

def ensure_directories():
    """Ensures that local directories exist."""
    for directory in [INCOMING_DIR, LOCAL_STAGING_DIR]:
        directory.mkdir(parents=True, exist_ok=True)

# Automatically ensure directories on import
ensure_directories()

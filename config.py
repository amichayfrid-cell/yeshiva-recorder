from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

INCOMING_DIR = DATA_DIR / "incoming"
SORTED_DIR = DATA_DIR / "sorted"
NEEDS_REVIEW_DIR = DATA_DIR / "needs_review"
HISTORY_FILE = DATA_DIR / "history.json"
MAX_HISTORY_ENTRIES = 500  # Maximum number of records to retain in history.json

# USB Ingestion Configuration
USB_DELETE_AFTER_INGEST = True  # Automatically wipe recorder after verified copy
USB_POLL_INTERVAL_SEC = 2.0
USB_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".wma"}

def ensure_directories():
    """Ensures that all necessary directories exist."""
    for directory in [INCOMING_DIR, SORTED_DIR, NEEDS_REVIEW_DIR]:
        directory.mkdir(parents=True, exist_ok=True)

# Automatically ensure directories on import
ensure_directories()

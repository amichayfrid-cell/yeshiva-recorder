import os
from pathlib import Path

# Load environment variables from .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Base Paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

INCOMING_DIR = DATA_DIR / "incoming"
SORTED_DIR = DATA_DIR / "sorted"
NEEDS_REVIEW_DIR = DATA_DIR / "needs_review"
LOCAL_BUFFER_DIR = DATA_DIR / "local_buffer"  # Local storage buffer before verified transfer to Yeshiva Server
HISTORY_FILE = DATA_DIR / "history.json"
NOTES_FILE = DATA_DIR / "notes.json"  # Student feedback and alerts storage
MAX_HISTORY_ENTRIES = 500  # Maximum number of records to retain in history.json

# Web Dashboard & Management API Configuration
WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.getenv("WEB_PORT", "8000"))
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "1234")  # Admin access password
STATIC_DIR = BASE_DIR / "web" / "static"

# Rav Tzvi Kostiner Protected Audio Library Directory
RAV_TZVI_DIR = Path(os.getenv("RAV_TZVI_DIR", str(DATA_DIR / "rav_tzvi")))

# Network Share (Windows Server - SMB / CIFS) Configuration
USE_NETWORK_SHARE = os.getenv("USE_NETWORK_SHARE", "False").lower() in ("true", "1", "yes")
SMB_SERVER_HOST = os.getenv("SMB_SERVER_HOST", "mdserver")
SMB_SHARE_NAME = os.getenv("SMB_SHARE_NAME", "שיעורי שמע")
SMB_MOUNT_POINT = Path(os.getenv("SMB_MOUNT_POINT", "/mnt/shiurei_shema"))
SMB_TARGET_SUBDIR_NAME = "שיעורים למיון"  # Target directory on the share for all processed files

# Speech-to-Text (STT) Configuration - ivrit.ai specialized Hebrew Whisper Large Turbo (Local Offline Model)
STT_MODEL_NAME = str(BASE_DIR / "ivrit_model")
STT_DEVICE = "cpu"
STT_COMPUTE_TYPE = "int8" # Fast CPU quantized inference

# AI Entity Extraction Configuration (LLM)
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma4:e2b"
AUDIO_CLIP_DURATION_SEC = 35 # 35 seconds is optimal for intro
AI_TIMEOUT_SEC = 180 # Generous timeout for CPU inference

# Known Yeshiva Rabbis for STT bias and LLM entity normalization
KNOWN_RABBIS = [
    "הרב אבי טילמן",
    "הרב אבינועם גולד",
    "הרב אביעד טורם",
    "הרב אודי הראל",
    "הרב אורי שטרנברג",
    "הרב אוריאל ספז",
    "הרב אלחנן אוריאל",
    "הרב אלי בזק",
    "הרב אלישיב מאיר",
    "הרב אמיר כץ",
    "הרב גיל-עד גנץ",
    "הרב דידי לנזמן",
    "הרב דרור שילה",
    "הרב חזי מעטו",
    "הרב יואל בן-דרור",
    "הרב יוסי הורביץ",
    "הרב יניב קרייף",
    "הרב יעקב גרוס",
    "הרב ישי רמות",
    "הרב מאיר קדוש",
    "הרב משה מאלי",
    "הרב נחמיה טאו",
    "הרב ניר שמשוני",
    "הרב נעם לנדאו",
    "הרב ערן היימן",
    "הרב צבי קוסטינר",
    "הרב קובי דביר",
    "הרב שמריהו הופמן",
]

# USB Ingestion Configuration
USB_DELETE_AFTER_INGEST = True  # Automatically wipe recorder after verified copy
USB_POLL_INTERVAL_SEC = 2.0
USB_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".wma"}

def ensure_directories():
    """Ensures that all necessary directories exist."""
    for directory in [INCOMING_DIR, SORTED_DIR, NEEDS_REVIEW_DIR, LOCAL_BUFFER_DIR, STATIC_DIR, RAV_TZVI_DIR]:
        directory.mkdir(parents=True, exist_ok=True)

# Automatically ensure directories on import
ensure_directories()

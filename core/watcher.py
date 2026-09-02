import os
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import List

import config
from core.hebrew_date import get_hebrew_date_str
from core.file_manager import (
    safe_move,
    get_unique_filepath,
    record_history,
    apply_id3_tags,
    cleanup_temp_files
)
from core.usb_ingest import start_usb_daemon

SUPPORTED_EXTENSIONS = config.USB_AUDIO_EXTENSIONS

def is_file_ready(filepath: Path, wait_seconds: float = 1.0) -> bool:
    """
    Checks if a file has finished being copied/written by comparing its size over time.
    """
    try:
        size1 = filepath.stat().st_size
        time.sleep(wait_seconds)
        size2 = filepath.stat().st_size
        return size1 == size2 and size1 > 0
    except OSError:
        return False

def get_file_timestamp(filepath: Path) -> datetime:
    """
    Extracts the original file creation/modification datetime.
    """
    try:
        stat = filepath.stat()
        return datetime.fromtimestamp(stat.st_mtime)
    except Exception:
        return datetime.now()

def generate_timestamp_filename(file_dt: datetime, original_extension: str = ".mp3") -> str:
    """
    Generates a standardized filename based on timestamp and Hebrew date.
    Format: 'YYYY-MM-DD_HH-MM-SS_(תאריך עברי).ext'
    Example: '2026-09-02_14-30-00_(י_אלול_תשפו).mp3'
    """
    date_time_str = file_dt.strftime("%Y-%m-%d_%H-%M-%S")
    hebrew_date = get_hebrew_date_str(file_dt).replace(" ", "_")
    return f"{date_time_str}_({hebrew_date}){original_extension}"

def process_single_audio_file(filepath: Path) -> Path:
    """
    Executes a fast, lightweight ingestion pipeline on a single audio file:
    1. Extracts original recording timestamp.
    2. Generates date-time based filename.
    3. Moves file directly to sorting queue (needs_review).
    4. Applies basic ID3 tags.
    5. Logs to history.
    """
    start_time = time.time()
    original_name = filepath.name
    ext = filepath.suffix.lower()
    file_dt = get_file_timestamp(filepath)
    hebrew_date_str = get_hebrew_date_str(file_dt)

    print(f"\n" + "=" * 60)
    print(f"[Ingestion] Processing file: {original_name}")
    print(f"[Ingestion] Original recording time: {file_dt.strftime('%Y-%m-%d %H:%M:%S')} ({hebrew_date_str})")

    # Generate timestamp filename
    target_filename = generate_timestamp_filename(file_dt, original_extension=ext)
    target_dir = config.NEEDS_REVIEW_DIR
    unique_target_path = get_unique_filepath(target_dir, target_filename)

    print(f"[Ingestion] Moving to sorting queue: {unique_target_path.name}")
    final_path = safe_move(str(filepath), unique_target_path)

    # Basic metadata for tagging & history
    metadata = {
        "rabbi": None,
        "topic": None,
        "status": "pending_manual_review",
        "recorded_at": file_dt.isoformat()
    }

    # Embed initial ID3 tags (Album = Hebrew Date, Title = Target Filename)
    try:
        apply_id3_tags(
            filepath=final_path,
            metadata=metadata,
            hebrew_date_str=hebrew_date_str
        )
    except Exception as e:
        print(f"[Ingestion] Warning: ID3 tagging skipped: {e}")

    # Record history
    duration_sec = round(time.time() - start_time, 2)
    record_history(
        original_filename=original_name,
        final_filepath=final_path,
        status="needs_review",
        metadata={
            **metadata,
            "duration_sec": duration_sec
        }
    )

    print(f"[Ingestion] ✓ Ready for manual sorting: {final_path.name} ({duration_sec}s)")
    print("=" * 60)
    return final_path

def process_inbox() -> List[Path]:
    """
    Scans incoming/ once and processes all available audio files.
    Returns list of processed paths.
    """
    processed_files = []
    if not config.INCOMING_DIR.exists():
        return processed_files

    for file_path in config.INCOMING_DIR.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
            if is_file_ready(file_path):
                res = process_single_audio_file(file_path)
                processed_files.append(res)
    return processed_files

def start_watching(poll_interval: float = 2.0) -> None:
    """
    Continuous background daemon loop monitoring incoming/.
    """
    print("=" * 60)
    print(f"[*] Lightweight Ingestion Watcher is ACTIVE")
    print(f"[*] Monitoring directory: {config.INCOMING_DIR}")
    print(f"[*] Target Sorting directory: {config.NEEDS_REVIEW_DIR}")
    print(f"[*] Poll interval: {poll_interval}s. Press Ctrl+C to stop.")
    print("=" * 60)

    # Initial cleanup
    cleanup_temp_files()

    # Start automatic USB ingestion daemon in background thread
    usb_thread = threading.Thread(target=start_usb_daemon, daemon=True)
    usb_thread.start()
    print("[*] USB Ingestion Daemon has been started in background.")

    try:
        while True:
            process_inbox()
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        print("\n[Watcher] Stopped by user.")

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
    Generates filename strictly in Hebrew date + time format without Gregorian date.
    Format: '(תאריך עברי) HH-MM.ext'
    Example: '(ח חשוון תשפו) 08-45.mp3'
    """
    time_str = file_dt.strftime("%H-%M")
    hebrew_date = get_hebrew_date_str(file_dt)
    return f"({hebrew_date}) {time_str}{original_extension}"

def sync_local_staging_to_network() -> None:
    """
    If central network share is online, flushes any local staging files to the network share.
    """
    if not config.NETWORK_TARGET_DIR.exists():
        return

    staging_dir = config.LOCAL_STAGING_DIR
    if not staging_dir.exists():
        return

    for file_path in staging_dir.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
            try:
                unique_dest = get_unique_filepath(config.NETWORK_TARGET_DIR, file_path.name)
                print(f"[Sync] Network online! Syncing {file_path.name} to central server...")
                safe_move(str(file_path), unique_dest)
                print(f"[Sync] ✓ Verified & transferred to central server: {unique_dest.name}")
            except Exception as e:
                print(f"[Sync] Error syncing {file_path.name} to network: {e}")

def process_single_audio_file(filepath: Path) -> Path:
    """
    Executes a verified, double-step pipeline on a single audio file:
    1. Extracts original recording timestamp and Hebrew date.
    2. Generates filename in format: '(תאריך עברי) שעה-דקה.mp3'.
    3. Resolves target: Network Share (\\mdserver\שיעורי שמע\שיעורים למיון) or Local Staging.
    4. Safely moves with SHA-256 integrity verification.
    5. Deletes local copy only upon 100% verified match in target.
    6. Logs to history.
    """
    start_time = time.time()
    original_name = filepath.name
    ext = filepath.suffix.lower()
    file_dt = get_file_timestamp(filepath)
    hebrew_date_str = get_hebrew_date_str(file_dt)

    print(f"\n" + "=" * 60)
    print(f"[Pipeline] Processing file: {original_name}")
    print(f"[Pipeline] Original recording time: {file_dt.strftime('%H:%M')} ({hebrew_date_str})")

    # Generate filename: '(תאריך עברי) HH-MM.mp3'
    target_filename = generate_timestamp_filename(file_dt, original_extension=ext)
    target_dir = config.get_final_target_dir()
    unique_target_path = get_unique_filepath(target_dir, target_filename)

    is_network = (target_dir == config.NETWORK_TARGET_DIR)
    target_label = "🏢 Central File Server (mdserver)" if is_network else "💾 Local Staging Buffer"
    print(f"[Pipeline] Destination: {target_label} -> {unique_target_path.name}")

    # Embed initial ID3 tags before move
    metadata = {
        "rabbi": None,
        "topic": None,
        "status": "needs_review",
        "recorded_at": file_dt.isoformat()
    }
    try:
        apply_id3_tags(
            filepath=filepath,
            metadata=metadata,
            hebrew_date_str=hebrew_date_str
        )
    except Exception as e:
        print(f"[Pipeline] ID3 tagging skipped: {e}")

    # Verified safe move (SHA-256 match before local delete)
    final_path = safe_move(str(filepath), unique_target_path)

    # Record history
    duration_sec = round(time.time() - start_time, 2)
    record_history(
        original_filename=original_name,
        final_filepath=final_path,
        status="synced_to_network" if is_network else "in_local_staging",
        metadata={
            **metadata,
            "duration_sec": duration_sec,
            "destination": str(final_path)
        }
    )

    print(f"[Pipeline] ✓ 100% Verified & Moved to {target_label}: {final_path.name} ({duration_sec}s)")
    print("=" * 60)
    return final_path

def process_inbox() -> List[Path]:
    """
    Scans incoming/ once and processes all available audio files.
    Also syncs any offline staging files to the network share.
    """
    # 1. Sync any local buffer files if network is available
    sync_local_staging_to_network()

    # 2. Process incoming files
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
    Continuous background daemon loop monitoring incoming/ and syncing to network.
    """
    print("=" * 60)
    print(f"[*] Double-Verification Ingestion Watcher is ACTIVE")
    print(f"[*] Monitoring directory: {config.INCOMING_DIR}")
    print(f"[*] Central Network Target: {config.NETWORK_TARGET_DIR}")
    print(f"[*] Local Staging Buffer: {config.LOCAL_STAGING_DIR}")
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

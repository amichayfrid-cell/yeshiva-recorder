import os
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import List

import config
from core.audio_processor import cut_audio
from core.transcriber import transcribe_audio
from core.ai_analyzer import extract_metadata_from_text, generate_target_filename
from core.hebrew_date import get_hebrew_date_str
from core.file_manager import (
    safe_move,
    get_unique_filepath,
    record_history,
    apply_id3_tags,
    cleanup_temp_files
)
from core.usb_ingest import start_usb_daemon
from core.network_share import (
    is_share_mounted,
    transfer_to_network_share,
    sync_local_buffer_to_network
)

SUPPORTED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".wma"}

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

def process_single_audio_file(filepath: Path) -> Path:
    """
    Executes the complete transactional production pipeline on a single audio file:
    1. Extracts original recording timestamp.
    2. Slices the first 35 seconds.
    3. Transcribes Hebrew speech via ivrit-ai Whisper STT.
    4. Extracts Rabbi + Topic via Gemma 4 LLM.
    5. Standardizes filename with Hebrew date.
    6. Safely moves from incoming to local_buffer (verifies SHA-256 & cleans incoming).
    7. Embeds ID3 tags into the local buffer audio file.
    8. If network share active: transfers to Windows Server (שיעורים למיון) & verifies SHA-256.
    9. Logs processing history.
    """
    start_time = time.time()
    print(f"\n" + "=" * 60)
    print(f"[Pipeline] Processing: {filepath.name}")
    print("=" * 60)

    original_name = filepath.name
    ext = filepath.suffix.lower()
    file_dt = get_file_timestamp(filepath)

    # Step 1: Cut audio slice
    print(f"[Pipeline 1/5] Truncating audio ({config.AUDIO_CLIP_DURATION_SEC}s)...")
    temp_cut_path = None
    try:
        temp_cut_path = cut_audio(str(filepath), duration_sec=config.AUDIO_CLIP_DURATION_SEC)
    except Exception as e:
        print(f"[Pipeline] Error cutting audio: {e}")

    # Step 2: Speech-to-Text with ivrit.ai
    transcript = ""
    if temp_cut_path:
        try:
            print(f"[Pipeline 2/5] Transcribing Hebrew audio with ivrit-ai ASR...")
            transcript = transcribe_audio(temp_cut_path)
        except Exception as e:
            print(f"[Pipeline] STT error: {e}")
        finally:
            try:
                os.remove(temp_cut_path)
            except OSError:
                pass

    # Step 3: Entity Extraction with Gemma 4
    print(f"[Pipeline 3/5] Extracting Rabbi and Topic with Gemma 4...")
    metadata = extract_metadata_from_text(transcript)

    # Step 4: Determine standardized filename & save to local buffer
    target_filename, is_identified = generate_target_filename(
        metadata,
        original_extension=ext,
        file_dt=file_dt
    )

    buffer_target_path = get_unique_filepath(config.LOCAL_BUFFER_DIR, target_filename)
    print(f"[Pipeline 4/5] Moving raw file to local buffer: {buffer_target_path.name}")
    buffered_path = safe_move(str(filepath), buffer_target_path)

    # Step 5: Embed ID3 tags into the buffered audio file
    if is_identified:
        apply_id3_tags(
            filepath=buffered_path,
            metadata=metadata,
            hebrew_date_str=get_hebrew_date_str(file_dt)
        )

    # Step 6: Transfer and verify to destination
    final_path = buffered_path
    if config.USE_NETWORK_SHARE:
        print(f"[Pipeline 5/5] Transferring to Yeshiva Server share ({config.SMB_TARGET_SUBDIR_NAME})...")
        server_path = transfer_to_network_share(buffered_path)
        if server_path:
            final_path = server_path
        else:
            print(f"[Pipeline 5/5] Share offline. File preserved in local buffer: {buffered_path.name}")
    else:
        # Local development / offline mode
        target_local_dir = config.SORTED_DIR if is_identified else config.NEEDS_REVIEW_DIR
        local_unique = get_unique_filepath(target_local_dir, target_filename)
        final_path = safe_move(str(buffered_path), local_unique)

    # Step 7: Record history
    duration_sec = round(time.time() - start_time, 2)
    record_history(
        original_filename=original_name,
        final_filepath=final_path,
        status="sorted" if is_identified else "needs_review",
        metadata={
            **metadata,
            "transcript": transcript,
            "duration_sec": duration_sec
        }
    )
    print(f"[Pipeline] ✓ Done: {final_path.name} ({duration_sec}s)")
    return final_path

def process_inbox() -> List[Path]:
    """
    Scans data/incoming/ once and processes all available audio files.
    Returns list of processed paths.
    """
    processed_files = []
    for file_path in config.INCOMING_DIR.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
            if is_file_ready(file_path):
                res = process_single_audio_file(file_path)
                processed_files.append(res)
    return processed_files

def start_watching(poll_interval: float = 3.0) -> None:
    """
    Continuous background daemon loop monitoring data/incoming/.
    """
    print("=" * 60)
    print(f"[*] Recording Automation Watcher is ACTIVE (ivrit-ai + Gemma 4)")
    print(f"[*] Monitoring directory: {config.INCOMING_DIR}")
    if config.USE_NETWORK_SHARE:
        mounted = is_share_mounted(config.SMB_MOUNT_POINT)
        status_str = "CONNECTED" if mounted else "OFFLINE (Staging Active)"
        print(f"[*] Windows Server Share: {config.SMB_MOUNT_POINT / config.SMB_TARGET_SUBDIR_NAME} [{status_str}]")
    else:
        print(f"[*] Target Sorted directory: {config.SORTED_DIR}")
        print(f"[*] Target Review directory: {config.NEEDS_REVIEW_DIR}")
    print(f"[*] Poll interval: {poll_interval} seconds. Press Ctrl+C to stop.")
    print("=" * 60)

    # Initial cleanup of stale temporary files
    cleanup_temp_files()

    # Start automatic USB ingestion daemon in background thread
    usb_thread = threading.Thread(target=start_usb_daemon, daemon=True)
    usb_thread.start()
    print("[*] USB Ingestion Daemon has been started automatically in background.")

    try:
        while True:
            if config.USE_NETWORK_SHARE:
                sync_local_buffer_to_network()
            process_inbox()
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        print("\n[Watcher] Stopped by user.")

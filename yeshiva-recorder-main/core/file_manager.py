import os
import shutil
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

import config

def calculate_sha256(filepath: str) -> str:
    """Calculates the SHA-256 hash of a file for integrity verification."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()

def get_unique_filepath(target_dir: Path, base_filename: str) -> Path:
    """
    Returns a unique file path in target_dir.
    If 'base_filename' already exists, appends '_1', '_2', etc., to prevent overwriting.
    """
    target_path = target_dir / base_filename
    if not target_path.exists():
        return target_path

    name_stem = target_path.stem
    extension = target_path.suffix
    counter = 1

    while True:
        candidate_name = f"{name_stem}_{counter}{extension}"
        candidate_path = target_dir / candidate_name
        if not candidate_path.exists():
            return candidate_path
        counter += 1

def safe_move(source_path: str, target_path: Path) -> Path:
    """
    Safely moves a file from source_path to target_path:
    1. Copies the file.
    2. Verifies SHA256 checksum match.
    3. Deletes the source file only upon verification.
    """
    source_p = Path(source_path)
    if not source_p.exists():
        raise FileNotFoundError(f"Source file does not exist: {source_path}")

    # Calculate source hash
    src_hash = calculate_sha256(source_path)

    # Ensure parent directory exists
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # Copy to destination
    shutil.copy2(source_path, str(target_path))

    # Verify destination hash
    dst_hash = calculate_sha256(str(target_path))
    if src_hash != dst_hash:
        # Checksum mismatch, clean up corrupted copy
        if target_path.exists():
            target_path.unlink()
        raise IOError(f"Checksum mismatch moving {source_path} to {target_path}!")

    # Safe to remove source file
    source_p.unlink()
    return target_path

def apply_id3_tags(
    filepath: Path,
    metadata: Dict[str, Any],
    hebrew_date_str: Optional[str] = None
) -> bool:
    """
    Writes ID3 metadata tags (Artist, Title, Album) into the MP3 audio file using mutagen.
    Artist = Rabbi name
    Title = Shiur topic
    Album = Hebrew date
    """
    if filepath.suffix.lower() != ".mp3":
        return False

    try:
        from mutagen.easyid3 import EasyID3
        from mutagen.mp3 import MP3
        from mutagen.id3 import ID3NoHeaderError

        file_str = str(filepath)
        try:
            audio = EasyID3(file_str)
        except ID3NoHeaderError:
            audio = MP3(file_str)
            audio.add_tags()
            audio.save()
            audio = EasyID3(file_str)

        rabbi = metadata.get("rabbi")
        topic = metadata.get("topic")

        if rabbi:
            audio["artist"] = [rabbi]
        if topic:
            audio["title"] = [topic]
        if hebrew_date_str:
            clean_date = hebrew_date_str.replace("_", " ")
            audio["album"] = [f"שיעורי תורה - {clean_date}"]

        audio.save()
        print(f"[ID3] ✓ Tags applied to {filepath.name}: Artist='{rabbi}', Title='{topic}'")
        return True
    except Exception as e:
        print(f"[ID3] Warning: Could not write ID3 tags to {filepath.name}: {e}")
        return False

def cleanup_temp_files() -> int:
    """
    Cleans up orphaned temporary audio files (tmp*.mp3, tmp*.wav)
    from workspace and system temp directory.
    Returns the number of deleted files.
    """
    import tempfile
    import glob

    deleted_count = 0
    patterns = [
        str(config.BASE_DIR / "tmp*.mp3"),
        str(config.BASE_DIR / "tmp*.wav"),
        os.path.join(tempfile.gettempdir(), "tmp*.mp3"),
        os.path.join(tempfile.gettempdir(), "tmp*.wav")
    ]

    for pattern in patterns:
        for file_path in glob.glob(pattern):
            try:
                # Only delete files older than 5 minutes to avoid deleting active slices
                mtime = os.path.getmtime(file_path)
                if (datetime.now().timestamp() - mtime) > 300:
                    os.remove(file_path)
                    deleted_count += 1
            except OSError:
                pass

    if deleted_count > 0:
        print(f"[Cleanup] Removed {deleted_count} stale temporary audio files.")
    return deleted_count

def record_history(
    original_filename: str,
    final_filepath: Path,
    status: str,
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    """
    Appends a processing record to data/history.json with automatic rotation (keeps last MAX_HISTORY_ENTRIES).
    """
    history_entry = {
        "timestamp": datetime.now().isoformat(),
        "original_filename": original_filename,
        "final_filepath": str(final_filepath),
        "status": status,
        "metadata": metadata or {},
        "sha256": calculate_sha256(str(final_filepath)) if final_filepath.exists() else None
    }

    history = []
    if config.HISTORY_FILE.exists():
        try:
            with open(config.HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        except (json.JSONDecodeError, OSError):
            history = []

    history.append(history_entry)

    # Log Rotation: Keep only the most recent N entries
    max_entries = getattr(config, "MAX_HISTORY_ENTRIES", 500)
    if len(history) > max_entries:
        history = history[-max_entries:]

    with open(config.HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

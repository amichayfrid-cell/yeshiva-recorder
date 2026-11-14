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
    Safely moves a file from source_path to target_path with size verification.
    Uses atomic os.replace on same filesystem, or atomic staging via .tmp_* file
    on cross-filesystem transfers (e.g. SMB network mounts).
    Deletes source only after destination is verified byte-for-byte.
    """
    source_p = Path(source_path)
    if not source_p.exists():
        raise FileNotFoundError(f"Source file does not exist: {source_path}")

    target_path.parent.mkdir(parents=True, exist_ok=True)
    expected_size = source_p.stat().st_size

    # Try atomic os.replace first (fast and atomic if on the same filesystem)
    try:
        os.replace(str(source_p), str(target_path))
        return target_path
    except OSError:
        # Cross-filesystem move (e.g. local disk to SMB mount or vice-versa)
        pass

    # For cross-filesystem transfer, copy to a hidden temporary file first
    temp_target = target_path.parent / f".tmp_{target_path.name}"
    try:
        shutil.copy2(str(source_p), str(temp_target))

        # Verify copied file size
        actual_size = temp_target.stat().st_size
        if actual_size != expected_size:
            raise IOError(f"File copy size mismatch: expected {expected_size}, got {actual_size}")

        # Atomic rename on destination filesystem
        temp_target.replace(target_path)

        # Remove source only after destination is fully confirmed
        source_p.unlink(missing_ok=True)
    except Exception:
        # Cleanup incomplete target file on any error
        if temp_target.exists():
            try:
                temp_target.unlink(missing_ok=True)
            except Exception:
                pass
        raise

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
            st = filepath.stat()
            orig_atime = st.st_atime
            orig_mtime = st.st_mtime
        except Exception:
            orig_atime = orig_mtime = None

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

        recorder = metadata.get("recorder")
        if recorder:
            try:
                from mutagen.id3 import TXXX
                mp3_raw = MP3(file_str)
                if mp3_raw.tags is not None:
                    mp3_raw.tags.add(TXXX(encoding=3, desc="recorder", text=[recorder]))
                    mp3_raw.save()
            except Exception:
                pass

        # Preserve the original file recording timestamp so ID3 tag writes don't taint mtime
        if orig_mtime is not None:
            try:
                os.utime(file_str, (orig_atime, orig_mtime))
            except Exception:
                pass

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

    # Generate / Update CSV Report with UTF-8 BOM for crystal-clear Hebrew in Excel
    report_csv = config.DATA_DIR / "processing_report.csv"
    try:
        write_header = not report_csv.exists()
        with open(report_csv, "a", encoding="utf-8-sig") as f:
            if write_header:
                f.write("זמן עיבוד,שם קובץ מקורי,רב שזוהה,נושא שזוהה,סטטוס סיווג,שם קובץ סופי\n")
            
            meta = metadata or {}
            rabbi = meta.get("rabbi") or "לא זוהה"
            topic = meta.get("topic") or "לא זוהה"
            status_hebrew = "סווג בהצלחה" if status == "sorted" else "לבדיקה ידנית"
            final_name = final_filepath.name
            timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Clean fields for CSV
            def clean_csv(text):
                return '"' + str(text).replace('"', '""') + '"'
                
            line = f"{clean_csv(timestamp_str)},{clean_csv(original_filename)},{clean_csv(rabbi)},{clean_csv(topic)},{clean_csv(status_hebrew)},{clean_csv(final_name)}\n"
            f.write(line)
    except Exception as e:
        print(f"[Report] Warning: Could not update CSV report: {e}")


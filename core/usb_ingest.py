import os
import sys
import time
from pathlib import Path
from typing import List, Set, Optional

import config
from core.file_manager import calculate_sha256, safe_move, get_unique_filepath

try:
    import psutil
except ImportError:
    psutil = None

import glob
import subprocess

def decode_hebrew_filename(filename: str) -> str:
    """Decodes improperly encoded Hebrew filenames (CP862/Windows-1255 to UTF-8)."""
    try:
        raw_bytes = filename.encode('latin1')
        for encoding in ['cp862', 'windows-1255', 'iso-8859-8']:
            try:
                decoded = raw_bytes.decode(encoding)
                if any('\u0590' <= c <= '\u05ff' for c in decoded):
                    return decoded
            except UnicodeDecodeError:
                pass
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return filename

def auto_mount_linux_usb():

    """
    On headless Linux servers (where USB drives aren't auto-mounted by a GUI),
    scans for unmounted USB block devices (/dev/sd[b-z][1-9]) and mounts them to /media/usb_sdX.
    """
    if sys.platform.startswith("win"):
        return

    sd_partitions = glob.glob("/dev/sd[b-z][1-9]")
    for dev in sd_partitions:
        try:
            # Check if device is already mounted
            res = subprocess.run(["findmnt", "-n", "-o", "TARGET", dev], capture_output=True, text=True)
            if res.stdout.strip():
                continue  # Already mounted

            # Try to auto-mount to /media/usb_<partition_name> with full permissions & Hebrew UTF-8 support
            mount_point = Path(f"/media/usb_{Path(dev).name}")
            subprocess.run(["sudo", "mkdir", "-p", str(mount_point)], capture_output=True, text=True)
            subprocess.run(["sudo", "mount", "-o", "umask=000,iocharset=utf8,codepage=862", dev, str(mount_point)], capture_output=True, text=True)

        except Exception:
            pass

def get_removable_mounts() -> List[Path]:
    """
    Detects currently mounted removable drives (USB sticks, digital recorders, SD cards).
    Works across Linux and Windows.
    """
    removable_paths = []
    if not psutil:
        return removable_paths

    # On Linux, try auto-mounting plugged-in USB partitions first
    auto_mount_linux_usb()

    partitions = psutil.disk_partitions(all=False)
    for p in partitions:
        mount = p.mountpoint
        opts = p.opts.lower()
        fstype = p.fstype.lower()

        # Windows detection: 'removable' option or FAT/FAT32/exFAT drives
        if sys.platform.startswith("win"):
            if "removable" in opts or "cdrom" not in opts and fstype in ("fat", "fat32", "exfat"):
                removable_paths.append(Path(mount))
        # Linux detection: mounts in /media, /run/media or vfat/exfat (EXCLUDE network shares)
        else:
            # Never treat CIFS/SMB/NFS network shares as removable USB drives!
            if fstype in ("cifs", "smb", "smb3", "nfs") or str(mount).startswith(str(config.NETWORK_MOUNT_POINT)):
                continue
            if any(mount.startswith(prefix) for prefix in ("/media", "/run/media")):
                removable_paths.append(Path(mount))
            elif "removable" in opts or fstype in ("vfat", "fat", "exfat", "msdos"):
                removable_paths.append(Path(mount))

    return removable_paths


def verify_audio_integrity(filepath: Path, expected_size: int) -> bool:
    """
    Verifies that the transferred audio file is intact and not corrupted:
    1. File exists and size matches expected_size exactly.
    2. File is not 0 bytes.
    3. Magic bytes / header check for audio format.
    4. Mutagen check if mutagen is installed.
    """
    if not filepath.exists():
        return False

    try:
        actual_size = filepath.stat().st_size
        if actual_size <= 0 or actual_size != expected_size:
            return False

        with open(filepath, "rb") as f:
            header = f.read(16)

        if len(header) < 4:
            return False

        ext = filepath.suffix.lower()
        if ext == ".mp3":
            # MP3 files start with ID3 tag or 0xFF sync frame
            if not (header.startswith(b"ID3") or header[0] == 0xFF):
                with open(filepath, "rb") as f:
                    chunk = f.read(1024)
                if b"ID3" not in chunk and b"\xff\xfb" not in chunk and b"\xff\xf3" not in chunk:
                    return False
        elif ext == ".wav":
            if not (header.startswith(b"RIFF") and b"WAVE" in header):
                return False

        try:
            import mutagen
            audio = mutagen.File(str(filepath))
            if audio is not None and getattr(audio, "info", None) is not None:
                if getattr(audio.info, "length", 0) <= 0:
                    return False
        except Exception:
            pass

        return True
    except Exception:
        return False

def get_drive_label(drive_path: Path) -> str:
    """
    Detects the custom name/label of a USB recorder drive.
    Checks:
    1. Root identification files on the USB drive (e.g. 'recorder.txt', 'id.txt', 'מקלט 4.txt', etc.)
    2. Linux filesystem volume label (via findmnt, lsblk, blkid, or /dev/disk/by-label)
    3. Windows filesystem volume label
    4. Mount point directory name
    Normalizes names like 'RECORDER_4', 'MIKLET 4', '4' -> 'מקלט 4'.
    Returns cleaned label (e.g. 'מקלט 4') or fallback 'מקלט שמע'.
    """
    from web import storage

    # 1. Check for identifier files on the root of the USB drive
    try:
        if drive_path.exists() and drive_path.is_dir():
            # Check for files like 'מקלט 4.txt', 'מקלט4.txt', 'recorder_4.txt'
            for item in drive_path.iterdir():
                if item.is_file():
                    name_lower = item.name.lower()
                    if name_lower.endswith((".txt", ".ini", ".id")):
                        base_stem = item.stem
                        normalized = storage.normalize_recorder_label(base_stem)
                        if normalized:
                            return normalized

            # Check content of standard id files (e.g. recorder.txt)
            for id_filename in ["recorder.txt", "id.txt", "name.txt", "label.txt", "מקלט.txt", "device.txt"]:
                id_file = drive_path / id_filename
                if id_file.exists() and id_file.is_file():
                    try:
                        content = id_file.read_text(encoding="utf-8", errors="ignore").strip()
                        if not content:
                            content = id_file.read_text(encoding="cp1255", errors="ignore").strip()
                        if content:
                            first_line = content.splitlines()[0].strip()
                            normalized = storage.normalize_recorder_label(first_line)
                            if normalized:
                                return normalized
                    except Exception:
                        pass
    except Exception:
        pass

    # 2. Linux volume label check
    if not sys.platform.startswith("win"):
        try:
            dev_res = subprocess.run(["findmnt", "-n", "-o", "SOURCE", str(drive_path)], capture_output=True, text=True, timeout=2)
            dev_source = dev_res.stdout.strip()
            if dev_source and dev_source.startswith("/dev/"):
                lbl_res = subprocess.run(["lsblk", "-no", "LABEL", dev_source], capture_output=True, text=True, timeout=2)
                raw_lbl = lbl_res.stdout.strip()
                if raw_lbl:
                    normalized = storage.normalize_recorder_label(raw_lbl)
                    if normalized:
                        return normalized

                blkid_res = subprocess.run(["blkid", "-s", "LABEL", "-o", "value", dev_source], capture_output=True, text=True, timeout=2)
                raw_blkid = blkid_res.stdout.strip()
                if raw_blkid:
                    normalized = storage.normalize_recorder_label(raw_blkid)
                    if normalized:
                        return normalized

            by_label_dir = Path("/dev/disk/by-label")
            if by_label_dir.exists() and dev_source:
                for link in by_label_dir.iterdir():
                    try:
                        if link.resolve() == Path(dev_source).resolve():
                            decoded_name = link.name.encode('utf-8').decode('unicode_escape')
                            normalized = storage.normalize_recorder_label(decoded_name)
                            if normalized:
                                return normalized
                    except Exception:
                        pass
        except Exception:
            pass

    # 3. Windows volume label check
    if sys.platform.startswith("win"):
        try:
            drive_letter = str(drive_path)[:2]
            if drive_letter.endswith(":"):
                vol_res = subprocess.run(["cmd", "/c", f"vol {drive_letter}"], capture_output=True, text=True, timeout=2)
                for line in vol_res.stdout.splitlines():
                    if "Volume in drive" in line and "is" in line:
                        raw = line.split("is")[-1].strip()
                        normalized = storage.normalize_recorder_label(raw)
                        if normalized:
                            return normalized
        except Exception:
            pass

    # 4. Check mount point name itself
    mount_name = drive_path.name
    normalized_mount = storage.normalize_recorder_label(mount_name)
    if normalized_mount:
        return normalized_mount

    return "מקלט שמע"

def copy_and_verify_from_usb(
    source_file: Path,
    target_dir: Path = config.INCOMING_DIR,
    delete_source: bool = config.USB_DELETE_AFTER_INGEST,
    target_name: Optional[str] = None,
    recorder_name: Optional[str] = None
) -> Optional[Path]:
    """
    Safely copies an audio file from a USB device into target_dir using atomic staging:
    1. Obtains expected source size.
    2. Copies to an isolated hidden temporary file (.part_*.part).
    3. If USB is disconnected or transfer is interrupted, immediately deletes the temporary file.
    4. Verifies byte-exact size and audio header integrity.
    5. Atomically renames temporary file to final target (os.replace).
    6. Only upon 100% verified transfer, deletes the original file from the USB recorder.
    """
    if not source_file.exists():
        return None

    try:
        expected_size = source_file.stat().st_size
    except (OSError, FileNotFoundError):
        print(f"[USB Ingest] Could not read source file (device disconnected?): {source_file}")
        return None

    if expected_size <= 0:
        print(f"[USB Ingest] Skipping empty 0-byte file: {source_file.name}")
        return None

    filename = target_name if target_name else source_file.name

    # Check if this exact file was already fully ingested in target_dir or needs_review
    target_candidate = target_dir / filename
    if target_candidate.exists() and target_candidate.stat().st_size == expected_size:
        print(f"[USB Ingest] File {filename} already fully ingested (size {expected_size} matches). Skipping duplicate.")
        if delete_source:
            try:
                source_file.unlink()
            except Exception:
                try:
                    subprocess.run(["sudo", "rm", "-f", str(source_file)], capture_output=True, text=True)
                except Exception:
                    pass
        return target_candidate

    unique_target = get_unique_filepath(target_dir, filename)
    
    # Temporary staging path in the same directory (enables atomic os.replace)
    temp_target = target_dir / f".part_{int(time.time()*1000)}_{unique_target.name}.part"
    temp_target.parent.mkdir(parents=True, exist_ok=True)

    print(f"[USB Ingest] Copying {source_file.name} ({round(expected_size / (1024*1024), 2)} MB) -> Staging...")

    copy_successful = False
    try:
        # Perform chunked copy to detect disconnections cleanly and promptly
        with open(source_file, "rb") as fsrc, open(temp_target, "wb") as fdst:
            while True:
                chunk = fsrc.read(1024 * 1024)  # 1MB buffer for fast USB transfer
                if not chunk:
                    break
                fdst.write(chunk)
            fdst.flush()
            os.fsync(fdst.fileno())

        # Copy metadata timestamps
        try:
            shutil.copystat(str(source_file), str(temp_target))
        except (OSError, Exception):
            pass

        # Verification Phase: Check exact size and audio validity
        if not verify_audio_integrity(temp_target, expected_size):
            actual_size = temp_target.stat().st_size if temp_target.exists() else 0
            raise IOError(f"Integrity check failed! Expected {expected_size} bytes, got {actual_size} bytes.")

        # Atomic Promotion: Move temp file to final destination
        os.replace(str(temp_target), str(unique_target))
        copy_successful = True
        print(f"[USB Ingest] ✓ 100% Verified on disk: {unique_target.name}")

        # Store recorder source mapping and embed in ID3
        if recorder_name:
            try:
                from web import storage
                storage.set_recorder_source(unique_target.name, recorder_name)
            except Exception:
                pass
            if unique_target.suffix.lower() == ".mp3":
                try:
                    from mutagen.mp3 import MP3
                    from mutagen.id3 import TXXX
                    audio = MP3(str(unique_target))
                    if audio.tags is None:
                        audio.add_tags()
                    audio.tags.add(TXXX(encoding=3, desc="recorder", text=[recorder_name]))
                    audio.save()
                except Exception:
                    pass

        # Delete source ONLY after verified copy
        if delete_source:
            try:
                source_file.unlink()
                print(f"[USB Ingest] ✓ Cleared from recorder: {source_file.name}")
            except Exception:
                try:
                    subprocess.run(["sudo", "rm", "-f", str(source_file)], capture_output=True, text=True)
                    print(f"[USB Ingest] ✓ Cleared via sudo rm: {source_file.name}")
                except Exception as del_err:
                    print(f"[USB Ingest] Note: Could not delete from recorder ({del_err}). Original kept on USB.")

        return unique_target

    except (OSError, IOError, Exception) as e:
        print(f"[USB Ingest] ✗ Interrupted or failed during copy of {source_file.name}: {e}")
        return None

    finally:
        # Rollback: Clean up any leftover temporary staging file if copy was not 100% successful
        if not copy_successful and temp_target.exists():
            try:
                temp_target.unlink(missing_ok=True)
                print(f"[USB Ingest] 🧹 Rollback: Cleaned up incomplete temporary file ({temp_target.name})")
            except Exception:
                pass

def scan_and_ingest_path(
    drive_path: Path,
    target_dir: Path = config.INCOMING_DIR,
    delete_source: bool = config.USB_DELETE_AFTER_INGEST,
    recorder_name: Optional[str] = None
) -> List[Path]:
    """
    Scans a given directory or USB drive recursively for audio recordings and ingests them.
    Automatically detects the recorder's specific name (e.g. 'מקלט 4') and attaches it to all files.
    """
    ingested_files = []
    if not drive_path.exists():
        print(f"[USB Ingest] Path does not exist: {drive_path}")
        return ingested_files

    rec_label = recorder_name or get_drive_label(drive_path)
    print(f"\n[USB Ingest] Scanning drive/folder: {drive_path} (🎙️ {rec_label})...")
    for root, _, files in os.walk(drive_path):
        for file in files:
            ext = Path(file).suffix.lower()
            if ext in config.USB_AUDIO_EXTENSIONS:
                file_path = Path(root) / file
                # Skip hidden/system files
                if file.startswith("."):
                    continue
                
                clean_name = decode_hebrew_filename(file)
                res = copy_and_verify_from_usb(
                    file_path, 
                    target_dir, 
                    delete_source, 
                    target_name=clean_name,
                    recorder_name=rec_label
                )
                if res:
                    ingested_files.append(res)

    print(f"[USB Ingest] Ingestion complete: {len(ingested_files)} file(s) ingested from {drive_path.name} ({rec_label}).")
    return ingested_files

def start_usb_daemon(
    poll_interval: float = config.USB_POLL_INTERVAL_SEC,
    delete_source: bool = config.USB_DELETE_AFTER_INGEST
) -> None:
    """
    Continuous background daemon monitoring for USB insertions.
    """
    print("=" * 60)
    print("[*] USB Ingestion Daemon is ACTIVE")
    print(f"[*] Target Directory: {config.INCOMING_DIR}")
    print(f"[*] Delete from recorder after copy: {delete_source}")
    print(f"[*] Polling interval: {poll_interval}s. Press Ctrl+C to stop.")
    print("=" * 60)

    known_drives: Set[Path] = set()

    try:
        while True:
            current_drives = set(get_removable_mounts())
            # Find newly attached drives
            new_drives = current_drives - known_drives
            for drive in new_drives:
                print(f"\n[USB Ingest] 🔌 New USB Device detected: {drive}")
                # Wait briefly for drive to settle
                time.sleep(1.0)
                scan_and_ingest_path(drive, delete_source=delete_source)

            known_drives = current_drives
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        print("\n[USB Ingest] Daemon stopped by user.")

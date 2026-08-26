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

            # Try to auto-mount to /media/usb_<partition_name> with full permissions
            mount_point = Path(f"/media/usb_{Path(dev).name}")
            subprocess.run(["sudo", "mkdir", "-p", str(mount_point)], capture_output=True, text=True)
            subprocess.run(["sudo", "mount", "-o", "umask=000", dev, str(mount_point)], capture_output=True, text=True)
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
        # Linux detection: mounts in /media, /mnt, /run/media or vfat/exfat
        else:
            if any(mount.startswith(prefix) for prefix in ("/media", "/run/media", "/mnt")):
                removable_paths.append(Path(mount))
            elif "removable" in opts:
                removable_paths.append(Path(mount))

    return removable_paths

def copy_and_verify_from_usb(
    source_file: Path,
    target_dir: Path = config.INCOMING_DIR,
    delete_source: bool = config.USB_DELETE_AFTER_INGEST
) -> Optional[Path]:
    """
    Safely copies an audio file from a USB device into target_dir:
    1. Generates unique target filename to prevent collisions.
    2. Uses safe_move (if deleting) or copy + SHA256 verification.
    3. Returns the path of the newly ingested file in target_dir.
    """
    if not source_file.exists():
        return None

    unique_target = get_unique_filepath(target_dir, source_file.name)
    print(f"[USB Ingest] Copying {source_file.name} -> {unique_target.name}...")

    try:
        if delete_source:
            try:
                final_path = safe_move(str(source_file), unique_target)
            except Exception:
                import shutil
                shutil.copy2(str(source_file), str(unique_target))
                src_hash = calculate_sha256(str(source_file))
                dst_hash = calculate_sha256(str(unique_target))
                if src_hash != dst_hash:
                    unique_target.unlink(missing_ok=True)
                    raise IOError("Checksum mismatch during USB copy!")
                subprocess.run(["sudo", "rm", "-f", str(source_file)], capture_output=True, text=True)
                final_path = unique_target

            print(f"[USB Ingest] ✓ Safely ingested & cleared from recorder: {source_file.name}")
            return final_path
        else:
            import shutil
            shutil.copy2(str(source_file), str(unique_target))
            # Verify checksum
            src_hash = calculate_sha256(str(source_file))
            dst_hash = calculate_sha256(str(unique_target))
            if src_hash != dst_hash:
                unique_target.unlink(missing_ok=True)
                raise IOError("Checksum mismatch during USB copy!")
            print(f"[USB Ingest] ✓ Safely ingested (original preserved): {source_file.name}")
            return unique_target
    except Exception as e:
        print(f"[USB Ingest] ✗ Error ingesting {source_file.name}: {e}")
        return None

def scan_and_ingest_path(
    drive_path: Path,
    target_dir: Path = config.INCOMING_DIR,
    delete_source: bool = config.USB_DELETE_AFTER_INGEST
) -> List[Path]:
    """
    Scans a given directory or USB drive recursively for audio recordings and ingests them.
    """
    ingested_files = []
    if not drive_path.exists():
        print(f"[USB Ingest] Path does not exist: {drive_path}")
        return ingested_files

    print(f"\n[USB Ingest] Scanning drive/folder: {drive_path}...")
    for root, _, files in os.walk(drive_path):
        for file in files:
            ext = Path(file).suffix.lower()
            if ext in config.USB_AUDIO_EXTENSIONS:
                file_path = Path(root) / file
                # Skip hidden/system files
                if file.startswith("."):
                    continue
                res = copy_and_verify_from_usb(file_path, target_dir, delete_source)
                if res:
                    ingested_files.append(res)

    print(f"[USB Ingest] Ingestion complete: {len(ingested_files)} file(s) ingested from {drive_path.name}.")
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

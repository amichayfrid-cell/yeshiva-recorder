import os
import shutil
from pathlib import Path
from typing import Tuple, List, Optional

import config
from core.file_manager import safe_move, get_unique_filepath, calculate_sha256

def is_share_mounted(mount_point: Optional[Path] = None) -> bool:
    """
    Checks whether the SMB/CIFS network share is properly mounted and writable.
    """
    target = mount_point or config.SMB_MOUNT_POINT
    if not target.exists():
        return False

    try:
        # Check if directory is accessible and test write capability with a hidden probe file
        test_file = target / ".write_test_probe"
        test_file.write_text("probe", encoding="utf-8")
        test_file.unlink(missing_ok=True)
        return True
    except (OSError, PermissionError):
        return False

def get_network_target_dir() -> Optional[Path]:
    """
    Returns the target directory on the Yeshiva Windows Server (שיעורים למיון) if mounted.
    Returns None if share is unmounted or unreachable.
    """
    if not getattr(config, "USE_NETWORK_SHARE", False):
        return None

    if is_share_mounted(config.SMB_MOUNT_POINT):
        target = config.SMB_MOUNT_POINT / config.SMB_TARGET_SUBDIR_NAME
        target.mkdir(parents=True, exist_ok=True)
        return target

    return None

def transfer_to_network_share(source_file: Path) -> Optional[Path]:
    """
    Safely transfers a processed audio file from the local buffer to the Yeshiva Windows Server:
    1. Copies to \\mdserver\\שיעורי שמע\\שיעורים למיון.
    2. Verifies SHA-256 checksum match on the destination share.
    3. Deletes the local buffer copy ONLY upon 100% verified match.
    """
    network_dir = get_network_target_dir()
    if not network_dir:
        print(f"[Network Share] ⚠️ Share unavailable. Keeping file in local buffer: {source_file.name}")
        return None

    unique_target = get_unique_filepath(network_dir, source_file.name)
    print(f"[Network Share] Uploading & verifying on Windows Server: {unique_target.name}...")
    try:
        final_server_path = safe_move(str(source_file), unique_target)
        print(f"[Network Share] ✓ Verified on Windows Server & removed from local buffer: {final_server_path.name}")
        return final_server_path
    except Exception as e:
        print(f"[Network Share] ✗ Transfer error: {e}. File preserved in local buffer.")
        return None

def sync_local_buffer_to_network() -> int:
    """
    Scans the local buffer directory (data/local_buffer/) and automatically uploads
    all pending recordings to the Windows Server share once network connectivity is live.
    Returns the number of successfully synced and verified files.
    """
    if not getattr(config, "USE_NETWORK_SHARE", False):
        return 0

    if not config.LOCAL_BUFFER_DIR.exists():
        return 0

    network_dir = get_network_target_dir()
    if not network_dir:
        return 0

    synced_count = 0
    buffer_files = [f for f in config.LOCAL_BUFFER_DIR.iterdir() if f.is_file() and not f.name.startswith(".")]

    if buffer_files:
        print(f"\n[Network Sync] 🔄 Windows Server reachable! Syncing {len(buffer_files)} buffered file(s) to '{network_dir.name}'...")

    for file_path in buffer_files:
        res = transfer_to_network_share(file_path)
        if res:
            synced_count += 1

    if synced_count > 0:
        print(f"[Network Sync] ✓ Sync complete: {synced_count} file(s) verified on Windows Server.\n")

    return synced_count

import os
import shutil
import subprocess
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

def get_active_target_dir() -> Tuple[Path, bool]:
    """
    Resolves the active target directory for processed audio files.
    Returns: (target_path, is_network_active)
    
    If network share is enabled and healthy:
      -> returns (SMB_MOUNT_POINT / SMB_TARGET_SUBDIR_NAME, True)
    If network share is enabled but offline/unreachable:
      -> returns (STAGING_DIR, False) with a warning log
    If network share is disabled (local mode):
      -> returns (SORTED_DIR, False)
    """
    if not getattr(config, "USE_NETWORK_SHARE", False):
        return config.SORTED_DIR, False

    network_target = config.SMB_MOUNT_POINT / config.SMB_TARGET_SUBDIR_NAME

    if is_share_mounted(config.SMB_MOUNT_POINT):
        network_target.mkdir(parents=True, exist_ok=True)
        return network_target, True

    # Network share enabled but currently unreachable -> Fallback to staging buffer
    print(f"[Network Share] ⚠️ Warning: Network share '{config.SMB_MOUNT_POINT}' unreachable. Buffering to local staging: {config.STAGING_DIR}")
    config.STAGING_DIR.mkdir(parents=True, exist_ok=True)
    return config.STAGING_DIR, False

def sync_staging_to_network() -> int:
    """
    Scans the local staging buffer and automatically transfers all buffered recordings
    to the Windows Server share (שיעורים למיון) once network connectivity is restored.
    Returns the number of synced files.
    """
    if not getattr(config, "USE_NETWORK_SHARE", False):
        return 0

    if not config.STAGING_DIR.exists():
        return 0

    if not is_share_mounted(config.SMB_MOUNT_POINT):
        return 0

    network_target = config.SMB_MOUNT_POINT / config.SMB_TARGET_SUBDIR_NAME
    network_target.mkdir(parents=True, exist_ok=True)

    synced_count = 0
    staging_files = [f for f in config.STAGING_DIR.iterdir() if f.is_file() and not f.name.startswith(".")]

    if staging_files:
        print(f"\n[Network Sync] 🔄 Network restored! Syncing {len(staging_files)} buffered file(s) to '{network_target.name}'...")

    for file_path in staging_files:
        try:
            unique_dest = get_unique_filepath(network_target, file_path.name)
            final_path = safe_move(str(file_path), unique_dest)
            print(f"[Network Sync] ✓ Transferred: {file_path.name} -> {final_path}")
            synced_count += 1
        except Exception as e:
            print(f"[Network Sync] ✗ Failed to transfer {file_path.name}: {e}")

    if synced_count > 0:
        print(f"[Network Sync] ✓ Sync complete: {synced_count} file(s) uploaded to Windows Server.\n")

    return synced_count

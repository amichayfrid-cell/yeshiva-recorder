import shutil
from pathlib import Path

import config


def test_ensure_directories_creates_required_local_dirs(tmp_path: Path, monkeypatch):
    new_data = tmp_path / "fresh_data"
    monkeypatch.setattr(config, "INCOMING_DIR", new_data / "incoming")
    monkeypatch.setattr(config, "LOCAL_STAGING_DIR", new_data / "needs_review")
    monkeypatch.setattr(config, "LOCAL_UPLOAD_DIR", new_data / "upload_lessons")

    config.ensure_directories()

    assert config.INCOMING_DIR.is_dir()
    assert config.LOCAL_STAGING_DIR.is_dir()
    assert config.LOCAL_UPLOAD_DIR.is_dir()


def test_is_network_share_mounted_false_when_missing_or_empty(monkeypatch):
    # Mount point does not exist yet
    assert config.is_network_share_mounted() is False

    # Exists and is_real_mount is True, but directory is empty
    config._MOUNT_CACHE = None
    config.NETWORK_MOUNT_POINT.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config, "_is_real_mount", lambda: True)
    assert config.is_network_share_mounted() is False

    # Only dot-files still counts as empty
    config._MOUNT_CACHE = None
    (config.NETWORK_MOUNT_POINT / ".hidden").write_text("x", encoding="utf-8")
    assert config.is_network_share_mounted() is False


def test_is_network_share_mounted_true_and_uses_cache(monkeypatch):
    config.NETWORK_MOUNT_POINT.mkdir(parents=True, exist_ok=True)
    (config.NETWORK_MOUNT_POINT / "שיעורים").mkdir()
    monkeypatch.setattr(config, "_is_real_mount", lambda: True)

    assert config.is_network_share_mounted() is True

    # Removing mount flag within 15s still returns cached True
    monkeypatch.setattr(config, "_is_real_mount", lambda: False)
    assert config.is_network_share_mounted() is True

    # Advancing cache time past TTL refreshes result
    config._MOUNT_CACHE_TIME -= 20.0
    assert config.is_network_share_mounted() is False


def test_get_final_target_dir_offline_and_online(monkeypatch):
    assert config.get_final_target_dir() == config.LOCAL_STAGING_DIR

    config.NETWORK_MOUNT_POINT.mkdir(parents=True, exist_ok=True)
    config.NETWORK_TARGET_DIR.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config, "is_network_share_mounted", lambda: True)

    assert config.get_final_target_dir() == config.NETWORK_TARGET_DIR


def test_get_upload_dirs_fallback_and_network_candidates(monkeypatch):
    # Fallback to LOCAL_UPLOAD_DIR when no network upload locations exist
    dirs = config.get_upload_dirs(force_refresh=True)
    assert dirs == [config.LOCAL_UPLOAD_DIR]
    assert config.get_upload_dir() == config.LOCAL_UPLOAD_DIR

    # When NETWORK_UPLOAD_MOUNT has audio and NETWORK_SHARE_UPLOAD_SUBDIR exists on mounted share
    config.NETWORK_UPLOAD_MOUNT.mkdir(parents=True, exist_ok=True)
    (config.NETWORK_UPLOAD_MOUNT / "lesson.mp3").write_bytes(b"ID3test")
    config.NETWORK_MOUNT_POINT.mkdir(parents=True, exist_ok=True)
    config.NETWORK_SHARE_UPLOAD_SUBDIR.mkdir(parents=True, exist_ok=True)
    extra_upload = config.NETWORK_MOUNT_POINT / "העלאת שיעורים ישנים"
    extra_upload.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(config, "is_path_mounted", lambda p: p == config.NETWORK_UPLOAD_MOUNT)
    monkeypatch.setattr(config, "is_network_share_mounted", lambda: True)

    dirs = config.get_upload_dirs(force_refresh=True)
    assert config.NETWORK_UPLOAD_MOUNT in dirs
    assert config.NETWORK_SHARE_UPLOAD_SUBDIR in dirs
    assert extra_upload in dirs
    assert config.LOCAL_UPLOAD_DIR not in dirs
    assert config.get_upload_dir() == config.NETWORK_UPLOAD_MOUNT

    # Cache invalidation test
    shutil.rmtree(config.NETWORK_UPLOAD_MOUNT)
    monkeypatch.setattr(config, "is_path_mounted", lambda p: False)
    monkeypatch.setattr(config, "is_network_share_mounted", lambda: False)
    # Cached result still includes previous dirs until invalidated
    assert config.NETWORK_UPLOAD_MOUNT in config.get_upload_dirs(force_refresh=False)
    config.invalidate_upload_dirs_cache()
    assert config.get_upload_dirs() == [config.LOCAL_UPLOAD_DIR]

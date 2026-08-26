import json
import shutil
from pathlib import Path
import config

def get_original_name_map():
    """Maps final file names / paths back to their original file names from history.json."""
    name_map = {}
    if not config.HISTORY_FILE.exists():
        return name_map

    try:
        with open(config.HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
            for entry in history:
                final_path_str = entry.get("final_filepath", "")
                orig_name = entry.get("original_filename", "")
                if final_path_str and orig_name:
                    filename = Path(final_path_str).name
                    name_map[filename] = orig_name
    except Exception as e:
        print(f"[Warning] Could not parse history.json: {e}")
    return name_map

def reset_files(restore_original_names: bool = True, clear_history: bool = True):
    print("=" * 60)
    print("Resetting files back to incoming directory...")
    print(f"Target: {config.INCOMING_DIR}")
    print("=" * 60)

    config.ensure_directories()
    orig_map = get_original_name_map() if restore_original_names else {}
    
    moved_count = 0
    source_dirs = [config.SORTED_DIR, config.NEEDS_REVIEW_DIR, config.STAGING_DIR]

    for source_dir in source_dirs:
        if not source_dir.exists():
            continue
        
        for file_path in list(source_dir.iterdir()):
            if file_path.is_file():
                # Determine target filename (restore original if available)
                orig_name = orig_map.get(file_path.name, file_path.name)
                target_path = config.INCOMING_DIR / orig_name
                
                # If target already exists, resolve collision
                counter = 1
                while target_path.exists():
                    stem = Path(orig_name).stem
                    suffix = Path(orig_name).suffix
                    target_path = config.INCOMING_DIR / f"{stem}_{counter}{suffix}"
                    counter += 1

                print(f"Moving: {file_path.name} -> {target_path.name}")
                shutil.move(str(file_path), str(target_path))
                moved_count += 1

    if clear_history and config.HISTORY_FILE.exists():
        try:
            config.HISTORY_FILE.unlink()
            print("History file (history.json) cleared.")
        except Exception as e:
            print(f"[Warning] Failed to clear history.json: {e}")

    # Remove any simulation test files from incoming
    for test_file in config.INCOMING_DIR.glob("REC_TEST*.mp3"):
        try:
            test_file.unlink()
        except OSError:
            pass

    print("=" * 60)
    print(f"✓ Done! Moved {moved_count} files back to incoming folder.")
    print("=" * 60)

if __name__ == "__main__":
    reset_files()

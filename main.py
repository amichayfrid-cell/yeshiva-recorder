import sys
from pathlib import Path
import config
from core.watcher import start_watching, process_inbox, process_single_audio_file

def print_help():
    print("Yeshiva Lesson Recording Automation")
    print("Usage:")
    print("  python main.py                  # Start continuous watcher on data/incoming/")
    print("  python main.py --watch          # Start continuous watcher")
    print("  python main.py --scan           # Process all files currently in data/incoming/ once")
    print("  python main.py <path_to_audio>  # Process a single audio file directly")

def main():
    if len(sys.argv) == 1 or (len(sys.argv) == 2 and sys.argv[1] in ["--watch", "-w"]):
        start_watching()
    elif len(sys.argv) == 2 and sys.argv[1] in ["--scan", "-s"]:
        print("[Main] Scanning incoming folder...")
        processed = process_inbox()
        print(f"[Main] Done. Processed {len(processed)} files.")
    elif len(sys.argv) == 2 and sys.argv[1] in ["--help", "-h"]:
        print_help()
    elif len(sys.argv) == 2:
        file_path = Path(sys.argv[1])
        if not file_path.exists():
            print(f"Error: File '{file_path}' not found.")
            sys.exit(1)
        process_single_audio_file(file_path)
    else:
        print_help()

if __name__ == "__main__":
    main()

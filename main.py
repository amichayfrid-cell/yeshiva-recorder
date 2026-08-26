import sys
import threading
from pathlib import Path
import uvicorn
import config
from core.watcher import start_watching, process_inbox, process_single_audio_file

def start_web_server():
    """Starts the FastAPI Web Server."""
    print(f"[*] Starting Web Dashboard on http://{config.WEB_HOST}:{config.WEB_PORT}")
    uvicorn.run("web.server:app", host=config.WEB_HOST, port=config.WEB_PORT, log_level="info")

def print_help():
    print("Yeshiva Lesson Recording Automation")
    print("Usage:")
    print("  python main.py                  # Start continuous watcher on data/incoming/")
    print("  python main.py --watch          # Start continuous watcher")
    print("  python main.py --web            # Start Web Management Dashboard & API only")
    print("  python main.py --all            # Start both Watcher and Web Dashboard concurrently")
    print("  python main.py --scan           # Process all files currently in data/incoming/ once")
    print("  python main.py <path_to_audio>  # Process a single audio file directly")

def main():
    if len(sys.argv) == 1 or (len(sys.argv) == 2 and sys.argv[1] in ["--watch", "-w"]):
        start_watching()
    elif len(sys.argv) == 2 and sys.argv[1] in ["--web"]:
        start_web_server()
    elif len(sys.argv) == 2 and sys.argv[1] in ["--all"]:
        # Run watcher in background thread and web server in main thread
        watcher_thread = threading.Thread(target=start_watching, daemon=True)
        watcher_thread.start()
        start_web_server()
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


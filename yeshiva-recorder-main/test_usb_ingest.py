import os
import sys
import argparse
from pathlib import Path
import config
from core.usb_ingest import scan_and_ingest_path, start_usb_daemon, get_removable_mounts

def run_simulation():
    print("=" * 60)
    print("🧪 USB Ingestion Simulation Test")
    print("=" * 60)

    sim_usb_dir = config.DATA_DIR / "simulated_usb"
    sim_usb_dir.mkdir(parents=True, exist_ok=True)

    # Create a dummy audio file in simulated USB
    dummy_file = sim_usb_dir / "REC_TEST_001.mp3"
    with open(dummy_file, "wb") as f:
        f.write(b"SIMULATED_AUDIO_DATA_FOR_TESTING_INGESTION_1234567890")

    print(f"[Sim] Created test file on simulated USB: {dummy_file}")
    print(f"[Sim] Running scan_and_ingest_path on: {sim_usb_dir}...")

    ingested = scan_and_ingest_path(sim_usb_dir, target_dir=config.INCOMING_DIR, delete_source=True)

    print(f"\n[Sim] Result:")
    for f in ingested:
        print(f"  • File in incoming/: {f.name} (exists={f.exists()})")
    print(f"  • Original on simulated USB exists?: {dummy_file.exists()} (Expected: False after wipe)")

    print("\n" + "=" * 60)
    print("✓ USB Ingestion simulation completed successfully!")
    print("=" * 60)

def main():
    parser = argparse.ArgumentParser(description="Test USB Ingestion Pipeline")
    parser.add_argument("--source", type=str, help="Specific drive or directory path to ingest from")
    parser.add_argument("--daemon", action="store_true", help="Start continuous USB auto-detection daemon")
    parser.add_argument("--list-drives", action="store_true", help="List currently detected removable drives")
    args = parser.parse_args()

    if args.list_drives:
        drives = get_removable_mounts()
        print(f"Detected removable mounts ({len(drives)}):")
        for d in drives:
            print(f"  - {d}")
    elif args.daemon:
        start_usb_daemon()
    elif args.source:
        scan_and_ingest_path(Path(args.source))
    else:
        run_simulation()

if __name__ == "__main__":
    main()

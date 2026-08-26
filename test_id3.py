import os
from pathlib import Path
from mutagen.easyid3 import EasyID3
import config

def inspect_sorted_id3_tags():
    print("=" * 60)
    print(" inspecting ID3 Tags in data/sorted/ ")
    print("=" * 60)

    sorted_files = list(config.SORTED_DIR.glob("*.mp3"))
    if not sorted_files:
        print("No MP3 files found in data/sorted/ yet.")
        return

    for audio_file in sorted_files:
        print(f"\nFile: {audio_file.name}")
        try:
            tags = EasyID3(str(audio_file))
            artist = tags.get("artist", ["N/A"])[0]
            title = tags.get("title", ["N/A"])[0]
            album = tags.get("album", ["N/A"])[0]
            print(f"  • Artist (הרב):  {artist}")
            print(f"  • Title  (נושא): {title}")
            print(f"  • Album  (תאריך): {album}")
        except Exception as e:
            print(f"  [!] Could not read ID3 tags: {e}")

    print("\n" + "=" * 60)

if __name__ == "__main__":
    inspect_sorted_id3_tags()

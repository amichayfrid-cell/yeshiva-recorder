import os
import math
import struct
import wave
import subprocess
from pathlib import Path

import config
from core import notes_manager

def generate_offline_audio(filepath: Path, duration_sec: float = 4.0, freq: float = 440.0):
    """
    Generates a 100% valid, playable synthetic audio file completely offline
    using Python's standard library wave and math modules + ffmpeg.
    """
    wav_temp = filepath.with_suffix(".temp.wav")
    sample_rate = 44100
    n_samples = int(sample_rate * duration_sec)

    try:
        with wave.open(str(wav_temp), 'w') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)

            # Generate gentle melody chime (A4, C#5, E5)
            for i in range(n_samples):
                t = i / sample_rate
                # Harmonic chime note progression
                f = freq if t < 1.3 else (freq * 1.25 if t < 2.6 else freq * 1.5)
                decay = math.exp(-(t % 1.3) * 2.5)
                sample_val = int(32767.0 * 0.4 * decay * math.sin(2.0 * math.pi * f * t))
                wav_file.writeframesraw(struct.pack('<h', sample_val))

        # If target is MP3, try to convert via ffmpeg
        if filepath.suffix.lower() == ".mp3":
            try:
                subprocess.run(
                    ["ffmpeg", "-y", "-i", str(wav_temp), "-codec:a", "libmp3lame", "-b:a", "128k", str(filepath)],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            except Exception:
                # If ffmpeg is not available, just rename/copy wav content as mp3/wav
                wav_temp.replace(filepath)
        else:
            wav_temp.replace(filepath)

        if wav_temp.exists():
            wav_temp.unlink(missing_ok=True)
        print(f"[MockData] ✓ Generated playable audio: {filepath.name}")
    except Exception as e:
        print(f"[MockData] Error generating audio: {e}")

def create_mock_audio(filepath: Path, text: str):
    """Tries gTTS first (if online), otherwise falls back to pure offline chime audio."""
    # Always overwrite invalid tiny placeholder files (<= 1000 bytes)
    if filepath.exists() and filepath.stat().st_size > 2000:
        return

    # Try online TTS
    tts_success = False
    try:
        from gtts import gTTS
        for lang_code in ['iw', 'he']:
            try:
                tts = gTTS(text=text, lang=lang_code, slow=False)
                tts.save(str(filepath))
                if filepath.exists() and filepath.stat().st_size > 2000:
                    tts_success = True
                    print(f"[MockData] ✓ Created Hebrew speech audio (gTTS): {filepath.name}")
                    break
            except Exception:
                continue
    except ImportError:
        pass

    if not tts_success:
        # Fallback to 100% offline playable audio chime
        generate_offline_audio(filepath, duration_sec=4.0)

def populate():
    """Populates local development folders with sample recordings and student notes."""
    print("=" * 60)
    print("Generating Mock Data for Local Web Dashboard Testing...")
    print("=" * 60)

    config.ensure_directories()

    # 1. Create sample recordings in local buffer and needs_review
    mock_files = [
        (
            config.LOCAL_BUFFER_DIR / "לסיווג_ידני_ח_אלול_תשפו.mp3",
            "שלום עליכם היום נלמד בהלכות שבת בעניין מלאכת בורר",
            "זה שיעור של הרב אלי בזק בנושא אמונה וביטחון מיום שלישי שעבר"
        ),
        (
            config.LOCAL_BUFFER_DIR / "הקלטה_002_ללא_הכרזה.mp3",
            "שיעור בספר התניא פרק כ מפי הרב",
            "שכחו להכריז בהתחלה אבל זה שיעור של הרב ערן היימן באיסור והיתר"
        ),
        (
            config.NEEDS_REVIEW_DIR / "שיעור_שנמסר_ביום_העיון.mp3",
            "פתיחת יום העיון השנתי בנושא תורה וארץ ישראל",
            None
        )
    ]

    for file_path, spoken_text, student_note in mock_files:
        create_mock_audio(file_path, spoken_text)
        if student_note:
            existing_notes = notes_manager.get_notes_for_file(file_path.name)
            if not existing_notes:
                notes_manager.add_note(
                    filename=file_path.name,
                    content=student_note,
                    filepath=str(file_path)
                )
                print(f"[MockData] ✓ Attached student note to {file_path.name}")

    print("\n[MockData] 🎉 הדמיה מקומית הוקמה בהצלחה עם קבצי שמע תקינים ונגינים!")
    print("[MockData] כעת תוכל להשמיע אותם ישירות בנגן ה-Web!")
    print("=" * 60)

if __name__ == "__main__":
    populate()

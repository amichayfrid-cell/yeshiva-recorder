import os
from typing import Optional
from faster_whisper import WhisperModel
import config

_model_instance: Optional[WhisperModel] = None

def build_initial_prompt() -> str:
    rabbis_str = ", ".join(config.KNOWN_RABBIS)
    return (
        f"הקלטת פתיח של שיעור תורה בישיבה. רבני הישיבה: {rabbis_str}. "
        "יום, תאריך עברי, אלול, תשפ\"ו, תשפ\"ד, תשפ\"ה, "
        "הרב, ראש הישיבה, שיעור כללי, שיעור עיון, "
        "מסכת, בבא מציעא, איסור והיתר, סוגיית, דרך הינוח, יאוש שלא מדעת, "
        "סימן, סעיף, חבורה, תפארת, שיחות הרצי\"ה, נתיב התשובה, אורות התשובה."
    )

def get_transcriber_model() -> WhisperModel:
    """
    Singleton loader for the ivrit-ai speech-to-text model.
    Loads once into memory and reuses across all audio files.
    """
    global _model_instance
    if _model_instance is None:
        print(f"[STT] Loading Hebrew ASR model '{config.STT_MODEL_NAME}' on {config.STT_DEVICE} ({config.STT_COMPUTE_TYPE})...")
        try:
            _model_instance = WhisperModel(
                config.STT_MODEL_NAME,
                device=config.STT_DEVICE,
                compute_type=config.STT_COMPUTE_TYPE
            )
        except Exception as e:
            print(f"[STT] Warning: Failed to load '{config.STT_MODEL_NAME}' ({e}). Falling back to 'turbo'...")
            _model_instance = WhisperModel("turbo", device=config.STT_DEVICE, compute_type=config.STT_COMPUTE_TYPE)
    return _model_instance

def transcribe_audio(audio_path: str) -> str:
    """
    Transcribes the given audio clip into Hebrew text with high accuracy.
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    model = get_transcriber_model()
    print(f"[STT] Transcribing Hebrew speech from: {os.path.basename(audio_path)}...")

    # Transcribe with Hebrew language constraint, Yeshiva vocabulary prompt, and VAD
    segments, info = model.transcribe(
        audio_path,
        language="he",
        initial_prompt=build_initial_prompt(),
        beam_size=5,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500)
    )

    transcript_parts = []
    for segment in segments:
        text = segment.text.strip()
        if text:
            transcript_parts.append(text)

    full_transcript = " ".join(transcript_parts).strip()
    print(f"[STT] Clean Hebrew Transcript: \"{full_transcript}\"")
    return full_transcript

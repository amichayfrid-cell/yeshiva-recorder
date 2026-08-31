import os
import subprocess
import tempfile
import urllib.request
import numpy as np
import config

try:
    import onnxruntime as ort
    import soundfile as sf
except ImportError:
    ort = None
    sf = None

VAD_MODEL_URL = "https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx"
VAD_MODEL_PATH = os.path.join(config.BASE_DIR, "silero_vad.onnx")

def download_vad_model():
    if not os.path.exists(VAD_MODEL_PATH):
        print("[VAD] Downloading Silero VAD ONNX model...")
        urllib.request.urlretrieve(VAD_MODEL_URL, VAD_MODEL_PATH)

def get_audio_segment_end(input_file: str, max_duration_sec: int = 60) -> float:
    """
    Reads the first max_duration_sec of audio and uses Silero VAD to find the 
    first continuous speech segment followed by silence. Returns the end time in seconds.
    """
    if ort is None or sf is None:
        print("[VAD] onnxruntime or soundfile missing, falling back to max duration.")
        return float(max_duration_sec)

    download_vad_model()
    
    fd, temp_wav = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    
    try:
        command = [
            "ffmpeg", "-y", "-i", input_file, 
            "-t", str(max_duration_sec), 
            "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", 
            temp_wav
        ]
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        audio, sample_rate = sf.read(temp_wav, dtype='float32')
        if len(audio) == 0:
            return float(max_duration_sec)
            
        session = ort.InferenceSession(VAD_MODEL_PATH, providers=["CPUExecutionProvider"])
        
        chunk_size = 512
        state = np.zeros((2, 1, 128), dtype=np.float32)
        
        speech_started = False
        silence_start_time = 0.0
        min_silence_duration = config.VAD_MIN_SILENCE_MS / 1000.0
        
        for i in range(0, len(audio), chunk_size):
            chunk = audio[i:i+chunk_size]
            if len(chunk) < chunk_size:
                chunk = np.pad(chunk, (0, chunk_size - len(chunk)), 'constant')
                
            ort_inputs = {
                'input': np.expand_dims(chunk, axis=0),
                'state': state,
                'sr': np.array([sample_rate], dtype=np.int64),
            }
            
            ort_outs = session.run(None, ort_inputs)
            speech_prob = ort_outs[0][0][0]
            state = ort_outs[1]
            
            current_time = (i + chunk_size) / sample_rate
            
            if speech_prob > 0.5:
                speech_started = True
                silence_start_time = 0.0 
            elif speech_started:
                if silence_start_time == 0.0:
                    silence_start_time = current_time
                elif current_time - silence_start_time >= min_silence_duration:
                    return current_time
                    
        return float(max_duration_sec)
        
    except Exception as e:
        print(f"[VAD] Error during VAD processing: {e}")
        return float(max_duration_sec)
    finally:
        if os.path.exists(temp_wav):
            os.remove(temp_wav)


def cut_audio(input_file: str, duration_sec: int = None) -> str:
    """
    Dynamically cuts the audio after the intro using VAD.
    """
    if duration_sec is None:
        duration_sec = getattr(config, 'AUDIO_CLIP_MAX_DURATION_SEC', 60)

    if not os.path.exists(input_file):
        raise FileNotFoundError(f"Input file not found: {input_file}")

    print(f"[VAD] Analyzing audio to find optimal cut point for {os.path.basename(input_file)}...")
    cut_time = get_audio_segment_end(input_file, duration_sec)
    
    cut_time = min(duration_sec, cut_time + 0.5)
    print(f"[VAD] Optimal cut time determined: {cut_time:.2f} seconds.")

    fd, output_path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    
    command = [
        "ffmpeg",
        "-y",
        "-i", input_file,
        "-t", str(cut_time),
        "-c", "copy",
        output_path
    ]
    
    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return output_path
    except subprocess.CalledProcessError:
        print("Warning: Stream copy failed, attempting to re-encode...")
        fallback_command = [
            "ffmpeg", "-y", "-i", input_file, "-t", str(cut_time), output_path
        ]
        subprocess.run(fallback_command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return output_path

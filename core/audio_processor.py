import os
import subprocess
import tempfile

def cut_audio(input_file: str, duration_sec: int = 60) -> str:
    """
    Cuts the first `duration_sec` seconds from `input_file` using ffmpeg
    and saves it to a temporary file.
    
    Returns the path to the temporary cut file.
    """
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"Input file not found: {input_file}")

    # Create a temporary file for the output
    fd, output_path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    
    # Run ffmpeg to extract the first N seconds
    command = [
        "ffmpeg",
        "-y",               # Overwrite output files without asking
        "-i", input_file,   # Input file
        "-t", str(duration_sec),  # Duration
        "-c", "copy",       # Copy codec (fastest, no re-encoding if we just slice)
        output_path
    ]
    
    try:
        # Run the command and capture output for error reporting
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return output_path
    except subprocess.CalledProcessError as e:
        # If the copy codec fails (e.g., format mismatch), try re-encoding
        print("Warning: Stream copy failed, attempting to re-encode...")
        fallback_command = [
            "ffmpeg",
            "-y",
            "-i", input_file,
            "-t", str(duration_sec),
            output_path
        ]
        subprocess.run(fallback_command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return output_path

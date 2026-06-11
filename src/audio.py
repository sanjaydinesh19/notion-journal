import tempfile
import threading
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd
from openai import OpenAI
from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner

console = Console()

SAMPLERATE = 16000
CHANNELS = 1


def record_audio(max_duration: int = 300) -> Path:
    """
    Record from the default microphone until Enter is pressed (or max_duration seconds).
    Returns path to a temporary WAV file.
    """
    frames = []
    stop_event = threading.Event()

    def _capture(indata, _frame_count, _time_info, _status):
        frames.append(indata.copy())

    def _wait_for_enter():
        input()
        stop_event.set()

    listener = threading.Thread(target=_wait_for_enter, daemon=True)
    listener.start()

    console.print("\n[bold green]Recording...[/] Press [bold]Enter[/] to stop.\n")

    with sd.InputStream(samplerate=SAMPLERATE, channels=CHANNELS, dtype="int16", callback=_capture):
        with Live(Spinner("dots", text="Listening"), refresh_per_second=10, console=console):
            stop_event.wait(timeout=max_duration)

    if not frames:
        raise RuntimeError("No audio captured.")

    audio = np.concatenate(frames, axis=0)

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    with wave.open(tmp.name, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)  # int16 = 2 bytes
        wf.setframerate(SAMPLERATE)
        wf.writeframes(audio.tobytes())

    return Path(tmp.name)


def transcribe(audio_path: Path, api_key: str) -> str:
    """Transcribe audio file using OpenAI Whisper."""
    client = OpenAI(api_key=api_key)

    console.print("[dim]Transcribing audio...[/]")
    with open(audio_path, "rb") as f:
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            response_format="text",
        )

    audio_path.unlink(missing_ok=True)
    return result.strip()

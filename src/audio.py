import json
import subprocess
import tempfile
import threading
import wave
from pathlib import Path
from typing import Optional

import numpy as np
from openai import OpenAI
from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner

console = Console()

_WHISPER_RATE = 16000
_TARGET_RMS = 500.0
_MAX_GAIN = 20.0


# ---------------------------------------------------------------------------
# PipeWire / Bluetooth helpers
# ---------------------------------------------------------------------------

def _pw_dump() -> list:
    try:
        out = subprocess.check_output(["pw-dump"], stderr=subprocess.DEVNULL, timeout=5)
        return json.loads(out)
    except Exception:
        return []


def _find_bt_device(dump: list) -> Optional[dict]:
    """Return the PipeWire Device object for the connected BT headset, or None."""
    for obj in dump:
        if obj.get("type") != "PipeWire:Interface:Device":
            continue
        props = obj.get("info", {}).get("props", {})
        if props.get("device.api") == "bluez5" and "bluez_card" in props.get("device.name", ""):
            return obj
    return None


def _get_bt_profile_index(device: dict, name_fragment: str) -> Optional[int]:
    profiles = device.get("info", {}).get("params", {}).get("EnumProfile", [])
    for p in profiles:
        if name_fragment in p.get("name", ""):
            return p["index"]
    return None


def _set_bt_profile(device_id: int, profile_index: int):
    subprocess.run(
        ["pw-cli", "set-param", str(device_id), "Profile", f"{{ index: {profile_index} }}"],
        stderr=subprocess.DEVNULL, timeout=5,
    )


def _get_bt_source_id(dump: list) -> Optional[int]:
    """Return PipeWire node ID of the BT mic source (Audio/Source), or None."""
    for obj in dump:
        if obj.get("type") != "PipeWire:Interface:Node":
            continue
        props = obj.get("info", {}).get("props", {})
        if (props.get("device.api") == "bluez5"
                and props.get("media.class") == "Audio/Source"):
            return obj.get("id")
    return None


# ---------------------------------------------------------------------------
# Recording
# ---------------------------------------------------------------------------

def _boost(audio: np.ndarray) -> np.ndarray:
    rms = np.sqrt(np.mean(audio.astype(np.float32) ** 2))
    if rms < _TARGET_RMS:
        gain = min(_TARGET_RMS / max(rms, 1.0), _MAX_GAIN)
        console.print(f"[dim]Applied {gain:.1f}x software gain (mic RMS={rms:.0f})[/]")
        return (audio.astype(np.float32) * gain).clip(-32768, 32767).astype(np.int16)
    return audio


def record_audio(max_duration: int = 300) -> Path:
    """
    Record from the best available mic source via PipeWire.
    If a Bluetooth headset is connected, switches it to HFP for mic access,
    records, then restores A2DP.
    Returns path to a 16kHz mono WAV file ready for Whisper.
    """
    dump = _pw_dump()
    bt_device = _find_bt_device(dump)
    a2dp_index = None
    source_target: Optional[str] = None

    # Switch BT headset to HFP if connected
    if bt_device:
        device_id = bt_device["id"]
        current_profile = (bt_device.get("info", {})
                           .get("params", {})
                           .get("Profile", [{}])[0]
                           .get("name", ""))

        # Remember current A2DP profile index so we can restore it
        a2dp_index = _get_bt_profile_index(bt_device, "a2dp-sink")

        if "headset" not in current_profile:
            # Prefer mSBC (wideband, 16kHz) over CVSD (narrowband, 8kHz)
            hfp_index = (_get_bt_profile_index(bt_device, "headset-head-unit-msbc")
                         or _get_bt_profile_index(bt_device, "headset-head-unit-cvsd")
                         or _get_bt_profile_index(bt_device, "headset-head-unit"))
            if hfp_index is not None:
                console.print(f"[dim]Switching headset to HFP profile for mic access...[/]")
                _set_bt_profile(device_id, hfp_index)
                import time; time.sleep(1.5)  # give PipeWire time to reconnect

        # Refresh dump to find the new source node
        dump = _pw_dump()
        src_id = _get_bt_source_id(dump)
        if src_id:
            source_target = str(src_id)

    # Build pw-record command
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    out_path = Path(tmp.name)
    tmp.close()

    cmd = ["pw-record", f"--rate={_WHISPER_RATE}", "--channels=1"]
    if source_target:
        cmd += [f"--target={source_target}"]
    cmd.append(str(out_path))

    stop_event = threading.Event()
    proc = subprocess.Popen(cmd, stderr=subprocess.DEVNULL)

    def _wait_for_enter():
        input()
        stop_event.set()
        proc.terminate()

    listener = threading.Thread(target=_wait_for_enter, daemon=True)
    listener.start()

    console.print("\n[bold green]Recording...[/] Press [bold]Enter[/] to stop.\n")

    with Live(Spinner("dots", text="Listening"), refresh_per_second=10, console=console):
        stop_event.wait(timeout=max_duration)
        if proc.poll() is None:
            proc.terminate()
        proc.wait()

    # Restore A2DP if we switched away
    if bt_device and a2dp_index is not None and "headset" not in (
        bt_device.get("info", {}).get("params", {}).get("Profile", [{}])[0].get("name", "")
    ):
        console.print("[dim]Restoring headset to A2DP...[/]")
        _set_bt_profile(bt_device["id"], a2dp_index)

    if not out_path.exists() or out_path.stat().st_size < 500:
        raise RuntimeError("No audio captured. Check that your microphone is connected.")

    with wave.open(str(out_path), "rb") as wf:
        raw = wf.readframes(wf.getnframes())
        channels = wf.getnchannels()
        rate = wf.getframerate()

    out_path.unlink(missing_ok=True)
    audio = np.frombuffer(raw, dtype=np.int16)

    # Mix to mono if needed
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1).astype(np.int16)

    rms = np.sqrt(np.mean(audio.astype(np.float32) ** 2))
    if rms < 3:
        raise RuntimeError(
            f"No audio signal detected (RMS={rms:.0f}). "
            "Make sure your microphone is not muted."
        )

    audio = _boost(audio)

    final = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    final_path = Path(final.name)
    final.close()

    with wave.open(str(final_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(audio.tobytes())

    console.print(f"[dim]Audio captured ({final_path.stat().st_size // 1024} KB, RMS={rms:.0f})[/]")
    return final_path


# ---------------------------------------------------------------------------
# Transcription
# ---------------------------------------------------------------------------

def transcribe(audio_path: Path, api_key: str) -> str:
    client = OpenAI(api_key=api_key)
    console.print("[dim]Transcribing audio...[/]")
    with open(audio_path, "rb") as f:
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            language="en",
            response_format="text",
        )
    audio_path.unlink(missing_ok=True)
    return result.strip()

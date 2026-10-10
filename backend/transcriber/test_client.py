"""
Test Client for Transcriber Service.
Use this to test the transcription pipeline before the frontend is built!

Usage:
  1. Test with laptop microphone:
     uv run python test_client.py --mic

  2. Test with a WAV audio file:
     uv run python test_client.py --file path/to/sample.wav

  3. Test synthetic audio / ping server:
     uv run python test_client.py
"""

import sys
import os
import json
import asyncio
import wave
from pathlib import Path
import numpy as np
import websockets

SAMPLE_RATE = 24000
CHUNK_DURATION = 0.08  # 80ms chunk
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_DURATION)  # 1920 samples
SERVER_URL = "ws://localhost:8000/ws/transcribe"
TRANSCRIPT_FILE = Path(__file__).resolve().parents[2] / "data" / "transcript.txt"


async def run_mic_streaming(ws):
    """Capture live microphone audio and stream to WebSocket."""
    import sounddevice as sd

    print("🎙️  Recording from microphone (24kHz 16-bit mono)...")
    print("👉 Speak into your mic! Press Ctrl+C to stop.")

    loop = asyncio.get_running_loop()
    audio_queue = asyncio.Queue()

    def callback(indata, frames, time, status):
        if status:
            print(f"Status: {status}", file=sys.stderr)
        # indata is float32 [-1.0, 1.0], convert to int16 PCM
        pcm_data = (indata[:, 0] * 32767).astype(np.int16).tobytes()
        loop.call_soon_threadsafe(audio_queue.put_nowait, pcm_data)

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        blocksize=CHUNK_SAMPLES,
        callback=callback,
    )

    with stream:
        try:
            while True:
                chunk = await audio_queue.get()
                await ws.send(chunk)
        except asyncio.CancelledError:
            pass


async def run_wav_streaming(ws, file_path: str):
    """Stream an existing WAV file in 80ms chunks."""
    path = Path(file_path)
    if not path.exists():
        print(f"❌ File not found: {file_path}")
        return

    print(f"📁 Streaming WAV file: {file_path}")
    with wave.open(str(path), "rb") as wf:
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        print(f"   Format: {n_channels} ch, {sampwidth*8}-bit, {framerate} Hz")

        while True:
            raw_frames = wf.readframes(CHUNK_SAMPLES)
            if not raw_frames:
                break
            await ws.send(raw_frames)
            await asyncio.sleep(CHUNK_DURATION)

    print("   Finished streaming audio file.")
    await ws.send(json.dumps({"action": "stop"}))


async def run_synthetic_streaming(ws, duration_seconds: int = 5):
    """Send synthetic audio frames to verify server connectivity."""
    print(f"🔊 Sending {duration_seconds}s of synthetic audio to test connection...")
    
    # 440 Hz soft sine wave
    t = np.linspace(0, CHUNK_DURATION, CHUNK_SAMPLES, endpoint=False)
    wave_data = (0.2 * np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16).tobytes()

    for _ in range(int(duration_seconds / CHUNK_DURATION)):
        await ws.send(wave_data)
        await asyncio.sleep(CHUNK_DURATION)

    print("   Finished sending synthetic audio.")
    await ws.send(json.dumps({"action": "stop"}))


async def listen_for_transcripts(ws):
    """Listen for incoming live transcriptions from the server."""
    try:
        async for message in ws:
            data = json.loads(message)
            msg_type = data.get("type")

            if msg_type == "ready":
                print("⚡ Server is ready for audio stream.")
            elif msg_type == "transcript":
                print(f"📝 Transcribed: {data.get('text')} (at {data.get('timestamp')})")
            elif msg_type == "error":
                print(f"❌ Server error: {data.get('message')}")
                break
    except websockets.exceptions.ConnectionClosed:
        pass


async def main():
    use_mic = "--mic" in sys.argv
    wav_path = None
    if "--file" in sys.argv:
        idx = sys.argv.index("--file")
        if idx + 1 < len(sys.argv):
            wav_path = sys.argv[idx + 1]

    print(f"Connecting to {SERVER_URL}...")
    try:
        async with websockets.connect(SERVER_URL) as ws:
            print("Connected to Transcriber server!")

            listener_task = asyncio.create_task(listen_for_transcripts(ws))

            # Select stream source
            if use_mic:
                sender_task = asyncio.create_task(run_mic_streaming(ws))
            elif wav_path:
                sender_task = asyncio.create_task(run_wav_streaming(ws, wav_path))
            else:
                sender_task = asyncio.create_task(run_synthetic_streaming(ws, duration_seconds=5))

            try:
                await sender_task
                # Allow a short moment for final transcription responses
                await asyncio.sleep(2)
            except KeyboardInterrupt:
                print("\nStopping...")
            finally:
                sender_task.cancel()
                listener_task.cancel()

    except Exception as e:
        print(f"❌ Connection error: {e}")
        print("💡 Make sure the server is running: uv run uvicorn main:app --reload")
        return

    # Print transcript file result
    print("\n--- Current data/transcript.txt ---")
    if TRANSCRIPT_FILE.exists():
        content = TRANSCRIPT_FILE.read_text(encoding="utf-8").strip()
        print(content if content else "(file is empty)")
    else:
        print("(file does not exist)")
    print("-----------------------------------")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExited.")

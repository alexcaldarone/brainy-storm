"""
Manual microphone/WAV demo client for the Transcriber Service.
Automated tests live in tests/; this client exercises the running service.

Usage:
  1. Test with laptop microphone:
     uv run python demo_client.py --mic

  2. Test with a WAV audio file:
     uv run python demo_client.py --file path/to/sample.wav

  3. Test synthetic audio / ping server:
     uv run python demo_client.py
"""

import sys
import json
import asyncio
import wave
from pathlib import Path
import numpy as np
import websockets
from websockets.exceptions import ConnectionClosed, InvalidURI

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
    except ConnectionClosed:
        pass


async def stream_until_complete(ws, audio_source, completion_timeout: float = 10):
    """Send stop once and wait for server closure, including after Ctrl+C."""
    sender = asyncio.create_task(audio_source)
    listener = asyncio.create_task(listen_for_transcripts(ws))
    try:
        done, _ = await asyncio.wait((sender, listener), return_when=asyncio.FIRST_COMPLETED)
        if sender in done:
            sender.result()
    except asyncio.CancelledError:
        # asyncio.run delivers the first Ctrl+C by cancelling its main task.
        print("\nStopping; waiting for the final transcript...")
    finally:
        if not sender.done():
            sender.cancel()
        await asyncio.gather(sender, return_exceptions=True)
        try:
            async with asyncio.timeout(completion_timeout):
                if not listener.done():
                    await ws.send(json.dumps({"action": "stop"}))
                await listener
        except TimeoutError:
            print("❌ Timed out waiting for transcript completion; the final save is unconfirmed.")
        except ConnectionClosed:
            pass
        finally:
            if not listener.done():
                listener.cancel()
            await asyncio.gather(listener, return_exceptions=True)


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

            # 1. Wait for server handshake/ready signal
            try:
                first_msg_raw = await ws.recv()
                first_msg = json.loads(first_msg_raw)
                if first_msg.get("type") == "error":
                    print(f"\n❌ Server Error: {first_msg.get('message')}\n")
                    return
                elif first_msg.get("type") == "ready":
                    print("⚡ Server confirmed: Ready for audio stream.")
            except ConnectionClosed as e:
                print(f"\n❌ Connection closed by server (code {e.code}): {e.reason or 'Policy violation / missing API key'}")
                return

            # 2. Select stream source
            if use_mic:
                audio_source = run_mic_streaming(ws)
            elif wav_path:
                audio_source = run_wav_streaming(ws, wav_path)
            else:
                audio_source = run_synthetic_streaming(ws, duration_seconds=5)
            await stream_until_complete(ws, audio_source)

    except InvalidURI:
        print(f"❌ Invalid URI: {SERVER_URL}")
        return
    except (ConnectionRefusedError, OSError):
        print("❌ Could not connect to server.")
        print("💡 Make sure the server is running: uv run uvicorn main:app --reload --port 8000")
        return
    except Exception as e:
        print(f"❌ Connection error: {e}")
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

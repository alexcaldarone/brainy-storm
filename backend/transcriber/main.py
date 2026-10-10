"""Transcribe the default microphone to a text file in five-second batches."""

import asyncio
import os
import sys
import termios
import tty
from contextlib import contextmanager
from pathlib import Path

import gradium
import sounddevice as sd
from dotenv import load_dotenv

WRITE_INTERVAL_SECONDS = 5
SAMPLE_RATE = 24000
BLOCK_SIZE = 1920  # 80 ms of audio
TRANSCRIPT_FILE = Path(__file__).resolve().parents[2] / "data" / "transcript.txt"


def write_batch(output, fragments):
    if fragments:
        text = " ".join(fragments)
        fragments.clear()
        output.write(text + "\n")
        output.flush()
        print(text, flush=True)


async def send_audio(stt, audio_queue):
    while True:
        await stt.send_audio(await audio_queue.get())


@contextmanager
def keyboard_controls(loop, on_key):
    stdin_fd = sys.stdin.fileno()
    settings = termios.tcgetattr(stdin_fd)
    try:
        tty.setcbreak(stdin_fd)  # Read Space immediately while preserving Ctrl+C.
        loop.add_reader(stdin_fd, on_key)
        yield
    finally:
        loop.remove_reader(stdin_fd)
        termios.tcsetattr(stdin_fd, termios.TCSADRAIN, settings)


async def main():
    if not sys.stdin.isatty():
        raise RuntimeError("Run this script in an interactive terminal to use Space and Ctrl+C")
    load_dotenv(Path(__file__).with_name(".env"))
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    api_key = os.getenv("GRADIUM_API_KEY", "").strip()
    if not api_key or api_key == "your-gradium-api-key-here":
        raise RuntimeError("Set GRADIUM_API_KEY in backend/transcriber/.env")

    loop = asyncio.get_running_loop()
    audio_queue = asyncio.Queue()
    paused = False

    def enqueue_audio(data):
        if not paused:
            audio_queue.put_nowait(data)

    def microphone_callback(indata, frames, time, status):
        if status:
            print(f"Microphone: {status}", file=sys.stderr)
        if not paused:
            loop.call_soon_threadsafe(enqueue_audio, bytes(indata))

    with sd.RawInputStream(
        samplerate=SAMPLE_RATE, channels=1, dtype="int16",
        blocksize=BLOCK_SIZE, callback=microphone_callback,
    ) as microphone:
        client = gradium.GradiumClient(api_key=api_key)
        stt = client.stt_realtime(
            model_name="default", input_format="pcm",
            json_config={"language": "en"}, wait_for_ready_on_start=True,
        )
        try:
            # Close SDK resources even if connection setup fails.
            await stt.__aenter__()
            TRANSCRIPT_FILE.parent.mkdir(parents=True, exist_ok=True)
            with TRANSCRIPT_FILE.open("w", encoding="utf-8") as output:
                fragments = []
                sender = asyncio.create_task(send_audio(stt, audio_queue))
                next_write = loop.time() + WRITE_INTERVAL_SECONDS
                keyboard_error = None

                def on_key():
                    nonlocal paused, next_write, keyboard_error
                    try:
                        key = os.read(sys.stdin.fileno(), 1)
                        if not key:
                            raise RuntimeError("Terminal input closed")
                        if key != b" ":
                            return
                        paused = not paused
                        if paused:
                            microphone.stop()
                            while not audio_queue.empty():
                                audio_queue.get_nowait()
                            write_batch(output, fragments)
                            print("Paused — press Space to resume.", flush=True)
                        else:
                            microphone.start()
                            next_write = loop.time() + WRITE_INTERVAL_SECONDS
                            print("Recording — press Space to pause.", flush=True)
                    except Exception as exc:
                        keyboard_error = exc
                        loop.remove_reader(sys.stdin.fileno())

                print(
                    f"Recording to {TRANSCRIPT_FILE}. Press Space to pause; Ctrl+C to stop.",
                    flush=True,
                )
                try:
                    with keyboard_controls(loop, on_key):
                        while True:
                            if keyboard_error is not None:
                                raise keyboard_error
                            if sender.done():
                                sender.result()
                            try:
                                message = await asyncio.wait_for(
                                    stt.recv(), timeout=max(0, next_write - loop.time()),
                                )
                            except TimeoutError:
                                pass  # A quiet stream still reaches the write deadline.
                            else:
                                if message is None or message.get("type") == "end_of_stream":
                                    break
                                if message.get("type") == "error":
                                    raise RuntimeError(f"Gradium: {message.get('message', message)}")
                                if message.get("type") == "text":
                                    text = " ".join(message.get("text", "").split())
                                    if text:
                                        fragments.append(text)
                            if loop.time() >= next_write:
                                write_batch(output, fragments)
                                next_write = loop.time() + WRITE_INTERVAL_SECONDS
                finally:
                    sender.cancel()
                    try:
                        write_batch(output, fragments)
                    finally:
                        await asyncio.gather(sender, return_exceptions=True)
        finally:
            await stt.__aexit__(None, None, None)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
    except Exception as exc:
        sys.exit(f"Transcriber error: {exc}")

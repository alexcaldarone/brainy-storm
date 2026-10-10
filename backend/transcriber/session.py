"""Supervise audio input, transcript output, and timed persistence together."""

import asyncio
import json
from datetime import datetime

from fastapi import WebSocketDisconnect

from batching import SessionBuffer, complete_before_cancel, periodic_flush

DRAIN_TIMEOUT_SECONDS = 5.0


async def transcribe_session(
    ws, stt, store, interval: float, *,
    drain_timeout: float = DRAIN_TIMEOUT_SECONDS,
    clock=None, sleep=asyncio.sleep,
) -> None:
    buffer = SessionBuffer(store)
    disconnected = asyncio.Event()
    clock = clock or asyncio.get_running_loop().time

    async def send_to_client(message):
        if disconnected.is_set():
            return
        try:
            await ws.send_json(message)
        except Exception:
            # Persistence and provider draining must survive a failed caption.
            disconnected.set()

    async def receive_audio():
        while True:
            try:
                message = await ws.receive()
            except (WebSocketDisconnect, OSError):
                disconnected.set()
                return
            if message["type"] == "websocket.disconnect":
                disconnected.set()
                return
            if message.get("bytes"):
                await stt.send_audio(message["bytes"])
            elif message.get("text"):
                try:
                    payload = json.loads(message["text"])
                except json.JSONDecodeError:
                    continue
                if not isinstance(payload, dict):
                    continue
                if payload.get("action") == "stop":
                    return
                if payload.get("action") == "flush":
                    await stt.send_flush()

    async def receive_text():
        async for message in stt:
            if message.get("type") == "text":
                text = buffer.add(message.get("text", ""))
                if text:
                    await send_to_client({
                        "type": "transcript",
                        "text": text,
                        "timestamp": datetime.now().strftime("%H:%M:%S"),
                    })
            elif message.get("type") == "error":
                raise RuntimeError(f"Gradium error: {message}")
            elif message.get("type") == "end_of_stream":
                return

    await send_to_client({"type": "ready", "message": "Ready to receive audio stream"})
    started_at = clock()
    audio = asyncio.create_task(receive_audio(), name="transcriber.audio")
    text = asyncio.create_task(receive_text(), name="transcriber.text")
    timer = asyncio.create_task(
        periodic_flush(buffer, interval, started_at=started_at, clock=clock, sleep=sleep),
        name="transcriber.timer",
    )
    disconnect = asyncio.create_task(disconnected.wait(), name="transcriber.disconnect")
    tasks = (audio, text, timer, disconnect)

    async def finalize():
        for task in tasks:
            if not task.done():
                task.cancel()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        # flush() finishes any pending append before acknowledging cancellation.
        # A failed append is latched in the buffer and will never be retried.
        await buffer.flush("final")
        for result in results:
            if isinstance(result, Exception):
                raise result

    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        if timer in done:
            timer.result()
        if text in done:
            text.result()
            return
        if audio in done:
            audio.result()

        # Client stop/disconnect: stop forwarding before sending EOS exactly once.
        if not audio.done():
            audio.cancel()
        await asyncio.gather(audio, return_exceptions=True)
        try:
            async with asyncio.timeout(drain_timeout):
                await stt.send_eos()
                done, _ = await asyncio.wait(
                    (text, timer), return_when=asyncio.FIRST_COMPLETED,
                )
                if timer in done:
                    timer.result()
                text.result()
        except TimeoutError as exc:
            raise RuntimeError(
                f"Gradium shutdown incomplete after {drain_timeout:g} seconds; "
                "only text received so far could be saved"
            ) from exc
    finally:
        await complete_before_cancel(finalize())

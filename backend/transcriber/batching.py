"""Timed transcript batches and a single-process, serialized file store."""

import asyncio
import logging
import math
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import TypeVar

logger = logging.getLogger("uvicorn.error")
T = TypeVar("T")


def parse_batch_seconds(value: str | None) -> float:
    try:
        seconds = float("5" if value is None else value)
    except ValueError:
        seconds = math.nan
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("TRANSCRIPT_BATCH_SECONDS must be a positive, finite number")
    return seconds


async def complete_before_cancel(operation: Awaitable[T]) -> T:
    """Finish an operation before propagating cancellation (including repeats).

    In particular, cancelling a to_thread await does not stop the filesystem
    operation. Locks and bookkeeping must stay alive until that operation ends.
    Operation failures take precedence over cancellation.
    """
    task = asyncio.ensure_future(operation)
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
    result = task.result()
    if cancelled:
        raise asyncio.CancelledError
    return result


class TranscriptStore:
    def __init__(self, path: Path):
        self.path = path
        self._lock = asyncio.Lock()
        self._active_sessions = 0
        self._content = ""

    async def _io(self, operation: Callable[[], T]) -> T:
        async with self._lock:
            return await complete_before_cancel(asyncio.to_thread(operation))

    async def initialize(self) -> None:
        def initialize():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.touch(exist_ok=True)
            self._content = self.path.read_text(encoding="utf-8")

        await self._io(initialize)

    @asynccontextmanager
    async def session(self):
        async with self._lock:
            self._active_sessions += 1
        try:
            yield
        finally:
            await complete_before_cancel(self._unregister())

    async def _unregister(self) -> None:
        async with self._lock:
            self._active_sessions -= 1

    def _append(self, line: str) -> None:
        with self.path.open("a", encoding="utf-8") as output:
            output.write(line)
            output.flush()
        self._content += line

    async def append(self, line: str) -> None:
        await self._io(lambda: self._append(line))

    async def read(self) -> str:
        async with self._lock:
            return self._content

    async def clear(self) -> bool:
        async with self._lock:
            if self._active_sessions:
                return False
            def clear():
                self.path.write_text("", encoding="utf-8")
                self._content = ""

            await complete_before_cancel(asyncio.to_thread(clear))
            return True


class TranscriptPersistenceError(RuntimeError):
    pass


class SessionBuffer:
    def __init__(self, store: TranscriptStore, timestamp: Callable[[], str] | None = None):
        self.store = store
        self._timestamp = timestamp or (lambda: datetime.now().strftime("%H:%M:%S"))
        self._fragments: list[str] = []
        self._flush_lock = asyncio.Lock()
        self.failure: TranscriptPersistenceError | None = None

    def add(self, text: str) -> str:
        text = " ".join(text.split())
        if text:
            self._fragments.append(text)
        return text

    async def flush(self, reason: str) -> None:
        # Protect the append AND removal from the buffer as one operation.
        await complete_before_cancel(self._flush(reason))

    async def _flush(self, reason: str) -> None:
        async with self._flush_lock:
            if self.failure is not None:
                raise self.failure  # Never retry a possibly partial append.
            if not self._fragments:
                return
            count = len(self._fragments)
            text = " ".join(self._fragments)
            timestamp = self._timestamp()
            try:
                await self.store.append(f"[{timestamp}] {text}\n")
            except Exception as exc:
                self.failure = TranscriptPersistenceError(
                    f"Transcript persistence failed; batch was not confirmed saved: {exc}"
                )
                logger.exception("Transcript append failed (%s flush)", reason)
                raise self.failure from exc
            del self._fragments[:count]
            logger.info(
                "Transcript batch saved: timestamp=%s fragments=%d characters=%d reason=%s",
                timestamp, count, len(text), reason,
            )


async def periodic_flush(
    buffer: SessionBuffer,
    interval: float,
    *,
    started_at: float,
    clock: Callable[[], float] | None = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> None:
    clock = clock or asyncio.get_running_loop().time
    deadline = started_at + interval
    while True:
        await sleep(max(0, deadline - clock()))
        await buffer.flush("periodic")
        # Keep the original cadence, skipping missed deadlines after slow I/O.
        next_tick = math.floor((clock() - started_at) / interval) + 1
        deadline = max(deadline + interval, started_at + next_tick * interval)

import asyncio
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from batching import SessionBuffer, TranscriptPersistenceError, parse_batch_seconds, periodic_flush
from helpers import ManualClock, RecordingStore, eventually


class ConfigurationTests(unittest.TestCase):
    def test_defaults_and_positive_numbers(self):
        for value, expected in ((None, 5), ("5", 5), ("0.25", 0.25), (" 2 ", 2)):
            with self.subTest(value=value):
                self.assertEqual(parse_batch_seconds(value), expected)

    def test_invalid_values(self):
        for value in ("", "0", "-1", "invalid", "inf", "-inf", "NaN"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "TRANSCRIPT_BATCH_SECONDS"):
                    parse_batch_seconds(value)


class BatchingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = self.enterContext(tempfile.TemporaryDirectory())
        self.store = RecordingStore(Path(self.directory) / "transcript.txt")
        await self.store.initialize()
        self.buffer = SessionBuffer(self.store, timestamp=lambda: "12:00:00")
        self.clock = ManualClock()
        self.tasks = []

    async def asyncTearDown(self):
        for task in self.tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)

    async def start_timer(self, interval=5):
        task = asyncio.create_task(periodic_flush(
            self.buffer, interval, started_at=self.clock(), clock=self.clock, sleep=self.clock.sleep,
        ))
        self.tasks.append(task)
        await eventually(lambda: self.clock.sleeping_until(interval))
        return task

    async def test_fragments_wait_for_deadline_and_flush_during_silence(self):
        await self.start_timer()
        self.buffer.add("Hello")
        self.clock.advance(2)
        self.buffer.add("world.")
        self.assertEqual(await self.store.read(), "")
        self.clock.advance(3)
        await eventually(lambda: self.clock.sleeping_until(10))
        self.assertEqual(self.store.writes, ["[12:00:00] Hello world.\n"])

    async def test_empty_intervals_do_not_write(self):
        await self.start_timer()
        self.clock.advance(5)
        await eventually(lambda: self.clock.sleeping_until(10))
        self.assertEqual(self.store.writes, [])

    async def test_continuous_speech_custom_interval_and_normalization(self):
        await self.start_timer(0.5)
        for index in range(3):
            self.buffer.add(f"  Part\n{index}\tready.  ")
            self.buffer.add(" \n\t")
            self.clock.advance(0.5)
            await eventually(lambda: self.clock.sleeping_until((index + 2) * 0.5))
        self.assertEqual(self.store.writes, [f"[12:00:00] Part {i} ready.\n" for i in range(3)])

    async def test_missed_deadlines_are_skipped(self):
        await self.start_timer()
        self.buffer.add("Delayed")
        self.clock.advance(16)
        await eventually(lambda: self.clock.sleeping_until(20))
        self.assertEqual(len(self.store.writes), 1)

    async def test_text_arriving_during_append_goes_in_next_batch(self):
        entered, release = asyncio.Event(), asyncio.Event()
        original = self.store.append

        async def append(line):
            entered.set()
            await release.wait()
            await original(line)

        with patch.object(self.store, "append", side_effect=append):
            self.buffer.add("First")
            task = asyncio.create_task(self.buffer.flush("periodic"))
            self.tasks.append(task)
            await entered.wait()
            self.buffer.add("Second")
            release.set()
            await task
        await self.buffer.flush("final")
        self.assertEqual(self.store.writes, ["[12:00:00] First\n", "[12:00:00] Second\n"])

    async def test_cancellation_keeps_io_locked_and_does_not_duplicate(self):
        entered = asyncio.Event()
        release = threading.Event()
        loop = asyncio.get_running_loop()
        original = self.store._append

        def blocked_append(line):
            loop.call_soon_threadsafe(entered.set)
            if not release.wait(2):
                raise TimeoutError("Test did not release the writer")
            original(line)

        self.buffer.add("Only once")
        with patch.object(self.store, "_append", side_effect=blocked_append):
            writer = asyncio.create_task(self.buffer.flush("periodic"))
            self.tasks.append(writer)
            await entered.wait()
            writer.cancel()
            reader = asyncio.create_task(self.store.read())
            self.tasks.append(reader)
            await asyncio.sleep(0)
            writer.cancel()  # A second cancellation must not release the lock.
            self.assertFalse(reader.done())
            self.assertFalse(writer.done())
            release.set()
            with self.assertRaises(asyncio.CancelledError):
                await writer
            self.assertEqual(await reader, "[12:00:00] Only once\n")
        await self.buffer.flush("final")
        self.assertEqual(len(self.store.writes), 1)

    async def test_partial_append_failure_is_not_retried(self):
        self.buffer.add("Cannot confirm saved")

        def partial_append(line):
            self.store.path.write_text(line[:6])
            raise OSError("Disk full")

        with patch.object(self.store, "_append", side_effect=partial_append) as append:
            with self.assertLogs("uvicorn.error", level="ERROR"):
                with self.assertRaises(TranscriptPersistenceError):
                    await self.buffer.flush("periodic")
            with self.assertRaises(TranscriptPersistenceError):
                await self.buffer.flush("final")
            self.assertEqual(append.call_count, 1)

    async def test_concurrent_sessions_have_separate_batches(self):
        other = SessionBuffer(self.store, timestamp=lambda: "12:00:00")
        self.buffer.add("Session A")
        other.add("Session B")
        await asyncio.gather(self.buffer.flush("final"), other.flush("final"))
        self.assertCountEqual((await self.store.read()).splitlines(), [
            "[12:00:00] Session A", "[12:00:00] Session B",
        ])

    async def test_clear_requires_all_sessions_to_finish(self):
        await self.store.append("Existing content\n")
        async with self.store.session():
            async with self.store.session():
                self.assertFalse(await self.store.clear())
            self.assertFalse(await self.store.clear())
            self.assertEqual(await self.store.read(), "Existing content\n")
        self.assertTrue(await self.store.clear())
        self.assertEqual(await self.store.read(), "")

    async def test_initialization_preserves_existing_file(self):
        await self.store.append("Previous session\n")
        await self.store.initialize()
        self.assertEqual(await self.store.read(), "Previous session\n")

    async def test_history_is_loaded_into_memory_and_new_batches_append(self):
        self.store.path.write_text("Existing history\n", encoding="utf-8")
        await self.store.initialize()
        with patch.object(Path, "read_text", side_effect=AssertionError("Must read memory")):
            self.assertEqual(await self.store.read(), "Existing history\n")
            await self.store.append("New recording\n")
            self.assertEqual(await self.store.read(), "Existing history\nNew recording\n")
            self.assertTrue(await self.store.clear())
            self.assertEqual(await self.store.read(), "")

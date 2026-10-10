import asyncio
import os
import tempfile
import unittest
from functools import partial
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import HTTPException, WebSocketDisconnect

import main
from helpers import FakeStt, FakeWebSocket, ManualClock, RecordingStore, eventually
from session import transcribe_session


class SessionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = self.enterContext(tempfile.TemporaryDirectory())
        self.store = RecordingStore(Path(self.directory) / "transcript.txt")
        await self.store.initialize()
        self.app = SimpleNamespace(state=SimpleNamespace(transcript_store=self.store, batch_seconds=5))
        self.request = SimpleNamespace(app=self.app)
        self.clock = ManualClock()
        self.stt = FakeStt()
        self.ws = FakeWebSocket(self.app)
        self.client = Mock()
        self.client.stt_realtime.return_value = self.stt
        self.enterContext(patch.object(main.gradium, "GradiumClient", return_value=self.client))
        self.enterContext(patch.object(main, "get_gradium_api_key", return_value="test-key"))
        self.enterContext(patch.object(main.logger, "exception"))
        self.enterContext(patch.object(main, "transcribe_session", partial(
            transcribe_session, clock=self.clock, sleep=self.clock.sleep,
        )))
        self.tasks = []

    async def asyncTearDown(self):
        for task in self.tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.assertFalse([
            task for task in asyncio.all_tasks()
            if task.get_name().startswith("transcriber.") and not task.done()
        ], "Session leaked a background task")

    async def start(self, wait_ready=True):
        task = asyncio.create_task(main.websocket_transcribe(self.ws))
        self.tasks.append(task)
        if wait_ready:
            await eventually(lambda: self.clock.sleeping_until(5))
        return task

    async def emit(self, text):
        self.stt.emit(text)
        await eventually(lambda: text in self.ws.captions())

    async def finish(self, task):
        self.ws.command("stop")
        await asyncio.wait_for(task, 2)

    async def test_stop_saves_partial_and_late_provider_results(self):
        self.stt.tail = ("late result",)
        task = await self.start()
        await self.emit("first result")
        self.assertEqual(await main.get_transcript(self.request), {"transcript": ""})
        await self.finish(task)
        self.assertEqual(self.stt.eos_count, 1)
        self.assertEqual(len(self.store.writes), 1)
        self.assertTrue(self.store.writes[0].endswith("first result late result\n"))
        self.assertEqual(self.ws.captions(), ["first result", "late result"])
        self.assertEqual(self.ws.close_code, 1000)
        self.assertTrue(self.stt.closed)
        self.assertTrue(await self.store.clear())
        self.client.stt_realtime.assert_called_once_with(
            model_name="default", input_format="pcm", json_config={"language": "en"},
            wait_for_ready_on_start=True,
        )

    async def test_audio_and_live_captions_continue_between_file_updates(self):
        task = await self.start()
        self.ws.messages.put_nowait({"type": "websocket.receive", "bytes": b"pcm"})
        await self.emit("live")
        await eventually(lambda: self.stt.audio == [b"pcm"])
        self.assertEqual(self.store.writes, [])
        self.clock.advance(5)
        await eventually(lambda: self.clock.sleeping_until(10))
        self.assertTrue((await main.get_transcript(self.request))["transcript"].endswith("live\n"))
        await self.finish(task)
        self.assertEqual(len(self.store.writes), 1)

    async def test_disconnect_message_drains_and_saves(self):
        self.stt.tail = ("tail",)
        task = await self.start()
        await self.emit("before disconnect")
        self.ws.disconnect()
        await asyncio.wait_for(task, 2)
        self.assertEqual(self.stt.eos_count, 1)
        self.assertTrue(self.store.writes[0].endswith("before disconnect tail\n"))
        self.assertEqual(self.ws.captions(), ["before disconnect"])

    async def test_disconnect_exception_drains_and_saves(self):
        task = await self.start()
        await self.emit("saved")
        self.ws.messages.put_nowait(WebSocketDisconnect())
        await asyncio.wait_for(task, 2)
        self.assertTrue(self.store.writes[0].endswith("saved\n"))

    async def test_failed_caption_send_does_not_stop_persistence(self):
        self.ws.fail_captions = True
        self.stt.tail = ("tail",)
        task = await self.start()
        self.stt.emit("caption failed")
        await asyncio.wait_for(task, 2)
        self.assertEqual(self.stt.eos_count, 1)
        self.assertTrue(self.store.writes[0].endswith("caption failed tail\n"))

    async def test_provider_error_saves_received_text_and_reports_failure(self):
        task = await self.start()
        await self.emit("received")
        self.stt.messages.put_nowait(RuntimeError("Provider failed"))
        await asyncio.wait_for(task, 2)
        self.assertTrue(self.store.writes[0].endswith("received\n"))
        self.assertEqual(self.ws.close_code, 1011)
        self.assertIn("Provider failed", self.ws.sent[-1]["message"])

    async def test_provider_finishing_first_stops_audio_receiver(self):
        task = await self.start()
        await self.emit("complete")
        self.stt.messages.put_nowait({"type": "end_of_stream"})
        await asyncio.wait_for(task, 2)
        self.assertEqual(self.stt.eos_count, 0)
        self.assertTrue(self.store.writes[0].endswith("complete\n"))
        self.assertEqual(self.ws.close_code, 1000)

    async def test_provider_drain_timeout_saves_text_and_reports_failure(self):
        self.stt.auto_end = False
        with patch.object(main, "transcribe_session", partial(
            transcribe_session, clock=self.clock, sleep=self.clock.sleep, drain_timeout=0.01,
        )):
            task = await self.start()
            await self.emit("before timeout")
            await self.finish(task)
        self.assertTrue(self.store.writes[0].endswith("before timeout\n"))
        self.assertEqual(self.ws.close_code, 1011)
        self.assertIn("shutdown incomplete", self.ws.sent[-1]["message"])

    async def test_timer_remains_active_during_drain(self):
        self.stt.auto_end = False
        task = await self.start()
        await self.emit("during drain")
        self.ws.command("stop")
        await eventually(lambda: self.stt.eos_count == 1)
        self.clock.advance(5)
        await eventually(lambda: self.clock.sleeping_until(10))
        self.assertTrue(self.store.writes[0].endswith("during drain\n"))
        self.assertFalse(task.done())
        self.stt.messages.put_nowait({"type": "end_of_stream"})
        await asyncio.wait_for(task, 2)

    async def test_timer_stop_race_writes_each_fragment_once(self):
        self.stt.tail = ("tail",)
        task = await self.start()
        await self.emit("before")
        self.clock.advance(5)
        self.ws.command("stop")
        await asyncio.wait_for(task, 2)
        text = await self.store.read()
        self.assertEqual(text.count("before"), 1)
        self.assertEqual(text.count("tail"), 1)
        self.assertLess(text.index("before"), text.index("tail"))

    async def test_cancellation_saves_received_text_and_unregisters(self):
        task = await self.start()
        await self.emit("cancelled")
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(self.store.writes[0].endswith("cancelled\n"))
        self.assertTrue(await self.store.clear())

    async def test_disk_failure_terminates_without_retry_or_success_close(self):
        task = await self.start()
        await self.emit("unsaved")
        with patch.object(self.store, "_append", side_effect=OSError("Disk full")) as append:
            self.clock.advance(5)
            await asyncio.wait_for(task, 2)
            self.assertEqual(append.call_count, 1)
        self.assertEqual(self.ws.close_code, 1011)
        self.assertIn("persistence failed", self.ws.sent[-1]["message"])
        self.assertEqual(self.store.writes, [])

    async def assert_clear_conflict(self):
        with self.assertRaises(HTTPException) as raised:
            await main.clear_transcript(self.request)
        self.assertEqual(raised.exception.status_code, 409)

    async def test_clear_conflicts_during_initialization_recording_and_drain(self):
        self.stt.enter_gate.clear()
        self.stt.auto_end = False
        task = await self.start(wait_ready=False)
        await self.stt.entered.wait()
        await self.assert_clear_conflict()
        self.stt.enter_gate.set()
        await eventually(lambda: self.clock.sleeping_until(5))
        await self.emit("kept")
        await self.assert_clear_conflict()
        self.ws.command("stop")
        await eventually(lambda: self.stt.eos_count == 1)
        await self.assert_clear_conflict()
        self.stt.messages.put_nowait({"type": "end_of_stream"})
        await asyncio.wait_for(task, 2)
        self.assertTrue((await self.store.read()).endswith("kept\n"))
        self.assertEqual(await main.clear_transcript(self.request), {
            "status": "cleared", "message": "Transcript file reset successfully",
        })
        self.assertEqual(await self.store.read(), "")

    async def test_clear_conflicts_while_final_append_is_pending(self):
        task = await self.start()
        await self.emit("final")
        entered, release = asyncio.Event(), asyncio.Event()
        original = self.store.append

        async def append(line):
            entered.set()
            await release.wait()
            await original(line)

        with patch.object(self.store, "append", side_effect=append):
            self.ws.command("stop")
            await entered.wait()
            await self.assert_clear_conflict()
            release.set()
            await asyncio.wait_for(task, 2)
        self.assertTrue(self.store.writes[0].endswith("final\n"))

    async def test_manual_provider_flush_does_not_bypass_timer(self):
        task = await self.start()
        await self.emit("waiting")
        self.ws.command("flush")
        await eventually(lambda: self.stt.flush_count == 1)
        self.assertEqual(self.store.writes, [])
        await self.finish(task)

    async def test_initialization_failure_unregisters(self):
        self.client.stt_realtime.side_effect = RuntimeError("Setup failed")
        task = await self.start(wait_ready=False)
        await asyncio.wait_for(task, 2)
        self.assertEqual(self.ws.close_code, 1011)
        self.assertTrue(await self.store.clear())

    async def test_failed_provider_connection_is_closed_and_unregistered(self):
        async def fail_setup():
            raise OSError("Connection setup failed")

        with patch.object(self.stt.enter_gate, "wait", side_effect=fail_setup):
            task = await self.start(wait_ready=False)
            await asyncio.wait_for(task, 2)
        self.assertTrue(self.stt.closed)
        self.assertEqual(self.ws.close_code, 1011)
        self.assertTrue(await self.store.clear())


class StartupTests(unittest.IsolatedAsyncioTestCase):
    async def test_valid_configuration_and_path_are_loaded_at_startup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data" / "transcript.txt"
            app = SimpleNamespace(state=SimpleNamespace())
            with patch.object(main, "TRANSCRIPT_FILE", path), patch.dict(
                os.environ, {"TRANSCRIPT_BATCH_SECONDS": "0.5"},
            ):
                async with main.lifespan(app):
                    self.assertEqual(app.state.batch_seconds, 0.5)
                    self.assertTrue(path.exists())
                    os.environ["TRANSCRIPT_BATCH_SECONDS"] = "7"
                    self.assertEqual(app.state.batch_seconds, 0.5)

    async def test_invalid_configuration_fails_before_touching_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "transcript.txt"
            app = SimpleNamespace(state=SimpleNamespace())
            with patch.object(main, "TRANSCRIPT_FILE", path), patch.dict(
                os.environ, {"TRANSCRIPT_BATCH_SECONDS": "NaN"},
            ):
                with self.assertRaisesRegex(ValueError, "TRANSCRIPT_BATCH_SECONDS"):
                    async with main.lifespan(app):
                        self.fail("Startup should fail")
                self.assertFalse(path.exists())

import asyncio
import contextlib
import io
import json
import unittest

from helpers import eventually
from demo_client import stream_until_complete


class ClientSocket:
    def __init__(self):
        self.sent = []
        self.messages = asyncio.Queue()

    async def send(self, message):
        self.sent.append(json.loads(message))

    def __aiter__(self):
        return self

    async def __anext__(self):
        message = await self.messages.get()
        if message is None:
            raise StopAsyncIteration
        return json.dumps(message)


class ManualClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_waits_for_close_after_audio_finishes(self):
        ws = ClientSocket()

        async def audio():
            return

        task = asyncio.create_task(stream_until_complete(ws, audio()))
        await eventually(lambda: ws.sent)
        self.assertFalse(task.done())
        self.assertEqual(ws.sent, [{"action": "stop"}])
        ws.messages.put_nowait(None)
        await task

    async def test_ctrl_c_stops_once_and_waits_for_final_result(self):
        ws = ClientSocket()
        started = asyncio.Event()

        async def audio():
            started.set()
            await asyncio.Event().wait()

        with contextlib.redirect_stdout(io.StringIO()):
            task = asyncio.create_task(stream_until_complete(ws, audio()))
            await started.wait()
            task.cancel()
            await eventually(lambda: ws.sent)
            self.assertFalse(task.done())
            ws.messages.put_nowait({"type": "transcript", "text": "final", "timestamp": "12:00:00"})
            ws.messages.put_nowait(None)
            await task
        self.assertEqual(ws.sent, [{"action": "stop"}])

    async def test_timeout_is_reported(self):
        ws = ClientSocket()
        with contextlib.redirect_stdout(io.StringIO()) as output:
            await stream_until_complete(ws, asyncio.sleep(0), completion_timeout=0.01)
        self.assertIn("final save is unconfirmed", output.getvalue())

    async def test_error_event_does_not_end_wait_before_server_closes(self):
        ws = ClientSocket()
        with contextlib.redirect_stdout(io.StringIO()):
            task = asyncio.create_task(stream_until_complete(ws, asyncio.sleep(0)))
            await eventually(lambda: ws.sent)
            ws.messages.put_nowait({"type": "error", "message": "Provider failed"})
            await eventually(ws.messages.empty)
            self.assertFalse(task.done())
            ws.messages.put_nowait(None)
            await task

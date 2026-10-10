import asyncio
import json

from batching import TranscriptStore


async def eventually(predicate):
    async with asyncio.timeout(2):
        while not predicate():
            await asyncio.sleep(0)


class ManualClock:
    def __init__(self):
        self.now = 0.0
        self.waiters = []

    def __call__(self):
        return self.now

    async def sleep(self, delay):
        future = asyncio.get_running_loop().create_future()
        self.waiters.append((self.now + delay, future))
        await future

    def advance(self, seconds):
        self.now += seconds
        for deadline, future in self.waiters:
            if deadline <= self.now and not future.done():
                future.set_result(None)

    def sleeping_until(self, deadline):
        return any(time == deadline and not future.done() for time, future in self.waiters)


class RecordingStore(TranscriptStore):
    def __init__(self, path):
        super().__init__(path)
        self.writes = []

    def _append(self, line):
        super()._append(line)
        self.writes.append(line)


class FakeStt:
    def __init__(self, *, tail=(), auto_end=True):
        self.messages = asyncio.Queue()
        self.tail = tail
        self.auto_end = auto_end
        self.eos_count = 0
        self.flush_count = 0
        self.audio = []
        self.entered = asyncio.Event()
        self.enter_gate = asyncio.Event()
        self.enter_gate.set()
        self.closed = False

    async def __aenter__(self):
        self.entered.set()
        await self.enter_gate.wait()
        return self

    async def __aexit__(self, *args):
        self.closed = True

    def emit(self, text):
        self.messages.put_nowait({"type": "text", "text": text})

    def __aiter__(self):
        return self

    async def __anext__(self):
        item = await self.messages.get()
        if isinstance(item, BaseException):
            raise item
        return item

    async def send_audio(self, audio):
        self.audio.append(audio)

    async def send_flush(self):
        self.flush_count += 1

    async def send_eos(self):
        self.eos_count += 1
        for text in self.tail:
            self.emit(text)
        if self.auto_end:
            self.messages.put_nowait({"type": "end_of_stream"})


class FakeWebSocket:
    def __init__(self, app=None, fail_captions=False):
        self.app = app
        self.messages = asyncio.Queue()
        self.sent = []
        self.close_code = None
        self.accepted = False
        self.fail_captions = fail_captions

    async def accept(self):
        self.accepted = True

    async def receive(self):
        message = await self.messages.get()
        if isinstance(message, BaseException):
            raise message
        return message

    async def send_json(self, message):
        if self.fail_captions and message["type"] == "transcript":
            raise OSError("Client disconnected")
        self.sent.append(message)

    async def close(self, code=1000):
        self.close_code = code

    def command(self, action):
        self.messages.put_nowait({"type": "websocket.receive", "text": json.dumps({"action": action})})

    def disconnect(self):
        self.messages.put_nowait({"type": "websocket.disconnect"})

    def captions(self):
        return [message["text"] for message in self.sent if message["type"] == "transcript"]

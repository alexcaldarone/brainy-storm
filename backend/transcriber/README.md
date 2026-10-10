# Transcriber Service

Real-time audio transcription service using **Gradium Speech-to-Text WebSocket API** for hackathon brainstorming sessions.

Continuously streams audio to Gradium and sends live captions to the frontend. Received text is buffered per recording and appended to `data/transcript.txt` every five seconds by default.

---

## 🚀 Quick Start

### 1. Add your Gradium API Key
Open `.env` (or copy from `.env.example`) and paste your API key:
```ini
GRADIUM_API_KEY=your_actual_gradium_api_key_here
TRANSCRIPT_BATCH_SECONDS=5
```

`TRANSCRIPT_BATCH_SECONDS` accepts any positive, finite number of seconds, including fractions. It defaults to `5` when absent. Invalid values fail startup. Restart the service after changing it.

### 2. Start the Server
From this directory (`backend/transcriber`):
```bash
uv run uvicorn main:app --reload --port 8000
```
The server will start at `http://localhost:8000`. Run one server worker: file locking and recording bookkeeping are shared within a single process.

## Transcript batches

Each session starts a monotonic timer when it becomes ready. At each deadline, the service appends one line containing the text received since its previous batch. Empty intervals produce no writes. Captions remain immediate.

```text
[14:36:15] We could build a service that groups the ideas discussed.
[14:36:20] Then another service could identify related suggestions.
```

The timestamp is local batch-formation time, not an audio timestamp. Recognition delay can move words into a later batch, and sentences may span batches. Whitespace is normalized; recognized words and punctuation are preserved without rewriting or deduplication.

On stop or disconnect, the service allows up to five seconds for Gradium's remaining results, then saves the final partial batch. File updates continue during this drain. Provider failures or timeouts preserve text already received and report an error to a connected client. A disk failure terminates the affected recording without automatically retrying an append that might be partial. Pending text is held in memory and cannot be recovered after a process crash.

`GET /transcript` returns only persisted text and is coordinated with appends. Services reading the file directly must process only newline-terminated lines and retain an incomplete trailing line for the next read; appends are not cross-process transactions. Concurrent recordings have separate buffers and append complete lines through one shared writer. Existing file contents are retained.

---

## Manual demo client

While the frontend is being developed, use `demo_client.py` to stream audio to the running service. Automated tests are separate in `tests/`.

### Option A: Test with your Laptop Microphone
```bash
uv run python demo_client.py --mic
```
Speak into your microphone, then press `Ctrl+C`. The client sends stop once and waits up to ten seconds for server closure before printing the saved transcript. With the default interval, speak for roughly twelve seconds: expect immediate captions, file entries around five and ten seconds, and a final partial batch after stopping.

### Option B: Test with a WAV Audio File
```bash
uv run python demo_client.py --file path/to/sample.wav
```

### Option C: Synthetic Audio Ping
```bash
uv run python demo_client.py
```

This sine-wave test checks connectivity; use speech to verify transcription batches.

## Automated tests

From this directory:

```bash
uv run python -m unittest discover -s tests -v
```

Tests use simulated Gradium streams, client WebSockets, controllable timing, and temporary files. They require no API key, microphone, or network, and do not modify the working transcript.

---

## 🔌 Frontend Integration Guide

When the frontend team builds the record button:

1. **Connect WebSocket**:
   ```javascript
   const ws = new WebSocket("ws://localhost:8000/ws/transcribe");
   ```

2. **Wait for ready**:
   ```javascript
   ws.onmessage = (event) => {
     const data = JSON.parse(event.data);
     if (data.type === "transcript") {
       console.log("Live transcript:", data.text);
     }
   };
   ```

3. **Stream Audio**:
   Capture audio via `AudioContext` / `AudioWorklet` (24kHz, 16-bit PCM mono) and send raw binary chunks:
   ```javascript
   ws.send(pcmChunk); // Int16Array.buffer
   ```

4. **Stop Session**:
   ```javascript
   ws.send(JSON.stringify({ action: "stop" }));
   ```

   Keep receiving until the server closes the WebSocket. A normal close (`1000`) confirms final persistence; an error event and close (`1011`) indicate failure. The existing `{ action: "flush" }` requests a Gradium flush but does not bypass the file batching timer.

---

## 📡 REST Endpoints

- `GET /health` – Check server status and if API key is configured.
- `GET /transcript` – View contents of `data/transcript.txt`.
- `POST /transcript/clear` – Reset `data/transcript.txt` for a new brainstorming session. Returns HTTP `409` while any recording is initializing, active, or saving its final results. Stop all recordings and wait for completion before clearing.

## Connected frontend

Run `npm run dev --prefix frontend` from the repository root alongside this
service. Vite proxies `/api` HTTP and WebSocket requests to port 8000.
For a separately hosted frontend, set `VITE_TRANSCRIBER_URL` to the service's
HTTP(S) URL at build time, or configure an equivalent `/api` reverse proxy.

Click **Start recording** and allow microphone access (localhost or HTTPS is
required). The frontend loads the existing backend transcript before sending
24 kHz mono PCM, displays live captions, and releases the microphone on pause
or stop. Both controls drain and save the recording before allowing a restart.
Export downloads the transcript currently held in the frontend's memory.
The backend has one shared transcript; the sidebar's sample boards do not
create separate backend recording sessions.

The store loads `data/transcript.txt` into memory on startup and updates that
memory after successful appends and clears. Restart the service to load edits
made directly to the file. The frontend retains history and live captions in
React state, including across pause/resume; reloading retrieves persisted history.

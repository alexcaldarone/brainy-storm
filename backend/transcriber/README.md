# Transcriber Service

Real-time audio transcription service using **Gradium Speech-to-Text WebSocket API** for hackathon brainstorming sessions.

Periodically receives audio streams from the frontend (or mic) and writes live transcribed text into `data/transcript.txt`.

---

## 🚀 Quick Start

### 1. Add your Gradium API Key
Open `.env` (or copy from `.env.example`) and paste your API key:
```ini
GRADIUM_API_KEY=your_actual_gradium_api_key_here
```

### 2. Start the Server
From this directory (`backend/transcriber`):
```bash
uv run uvicorn main:app --reload --port 8000
```
The server will start at `http://localhost:8000`.

---

## 🧪 Testing (Before Frontend is Ready)

While the frontend is being developed, you can test the transcription pipeline immediately using `test_client.py`:

### Option A: Test with your Laptop Microphone
```bash
uv run python test_client.py --mic
```
Speak into your microphone, then press `Ctrl+C`. Check `../../data/transcript.txt` to see your words written in real time!

### Option B: Test with a WAV Audio File
```bash
uv run python test_client.py --file path/to/sample.wav
```

### Option C: Synthetic Audio Ping
```bash
uv run python test_client.py
```

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

---

## 📡 REST Endpoints

- `GET /health` – Check server status and if API key is configured.
- `GET /transcript` – View contents of `data/transcript.txt`.
- `POST /transcript/clear` – Reset `data/transcript.txt` for a new brainstorming session.

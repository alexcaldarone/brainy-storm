<h1 align="center">Brainy Storm</h1>

> A real-time brainstorming companion that **listens** to your team, extracts ideas on the fly, and **enriches** them with live critique and competitor research.

https://github.com/alexcaldarone/tech-europe-agentic-hack/raw/main/public/demo.mp4

Brainstorming sessions often lose momentum to note-taking: good ideas get buried in discussion, tangents derail focus, and competitor research happens days later—if at all.

Brainy Storm listens to your conversation in real time, structures emerging ideas into a live board, and tracks which topic the room is actively debating. While you talk, background agents analyze pros and cons and search the web for real-world competitors, turning raw conversation into an actionable strategy board before the meeting ends.

## How It Works

Services communicate asynchronously through an append-only file pubsub (`pubsub/`), keeping real-time speech streaming decoupled from deep model reasoning:

- **Streaming Transcription**: The browser captures 24 kHz mono PCM and streams it over WebSocket to the transcriber service, which feeds [Gradium](https://gradium.ai) for low-latency ASR and appends to the live transcript.
- **Idea Engine**: A fast [Gemini](https://ai.google.dev/) agent polls transcript chunks with a sliding context window. It extracts new ideas, merges updates into existing ones, and tracks which card the room is currently discussing.
- **Deep Enrichment**: In the background, parallel Gemini workers analyze each idea without blocking the live session:
  - **Pros & Cons**: Evaluates categorized trade-offs (Technical, Business, User Experience, Operations, Financial) with impact levels.
  - **Competitors**: Uses Google Search grounding to find active competitors, market landscape, and key differentiators.
- **Live Board**: A React + TypeScript frontend polls updates every second, highlighting the active discussion card and rendering live debate insights.

## Quickstart

**Requirements:** Docker and Docker Compose, a [Gradium](https://gradium.ai) API key, and a [Gemini](https://ai.google.dev/) API key.

```bash
cp .env.example .env   # set GRADIUM_API_KEY and GEMINI_API_KEY
docker compose up --build
```

1. Open **http://localhost:5173**.
2. Allow microphone access and press **Start**.
3. Speak naturally—ideas, critiques, and competitors will populate the board in real time.

Settings (models, chunk sizes, polling intervals) live in `configs/default.yaml`. Stop the stack with `docker compose down`.


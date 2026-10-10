# {Tech: Europe} Zurich Agentic AI Hack

<p align="center">
  <a href="https://drive.google.com/file/d/1SAJt3qMT15nwZS-8X08hiZE9KjyscsY8/view"><strong>Watch the demo</strong></a>
</p>

## What this is

**Brainy Storm** is a shared workspace that turns a team's spoken brainstorming session into organized, evolving ideas. People stay in the conversation while AI handles transcription, idea tracking, summaries, arguments, competitor research, open questions, and system design.

Each idea receives a stable ID and its own record containing the relevant transcript excerpts, current summary, categorized pros and cons, assumptions, open questions, competitors, workflow, system architecture, thumbnail, and generated artifacts.

## Why we built this

We spent so much time trying to come up with ideas for this hackathon that the brainstorming process itself became our problem to solve.

We kept moving between ideas, raising objections, checking whether something already existed, and circling back to earlier suggestions. Keeping track of all that took attention away from the discussion. We wanted a tool that could follow the conversation with us and preserve the useful parts as our thinking changed.

So we built Brainy Storm: a brainstorming companion that helps a team remember what it considered, why an idea mattered, and what it still needs to decide.

## Architecture

The live loop is:

```text
Browser microphone
  -> Gradium transcriber
  -> data/transcript.txt
  -> Gemini idea classifier
  -> pubsub/classified-chunks.jsonl
  -> enrichment router and queue
  -> parallel Gemini enrichment agents
  -> data/ideas.json + data/ideas/<idea-id>/
  -> React idea board
```

![Brainy Storm system diagram: audio flows through Gradium transcription into a transcript; the Gemini-powered engine and enrichment service maintain ideas for the frontend.](public/diagram.png)

### Main components

| Component | Responsibility |
| --- | --- |
| **Frontend — React, TypeScript, Vite** | Captures microphone audio, displays live captions and idea cards, polls enriched ideas, and presents editable notes and static generated diagrams. |
| **Transcriber — Python, FastAPI, Gradium** | Receives browser audio over WebSocket, streams it to Gradium, returns captions, and persists transcript batches. |
| **Idea engine — Python, Gemini** | Reads new transcript chunks, recognizes new and existing ideas, assigns stable IDs, and publishes classified chunk/idea pairs. |
| **Enrichment API — Python, FastAPI, Gemini** | Stores ideas, exposes API and queue endpoints, and runs summary, pros/cons, workflow, architecture, and competitor agents. |
| **Classified-chunk worker** | Tails JSONL, checkpoints its byte offset, and submits each chunk to the enrichment queue exactly once. |
| **File storage** | Retains the raw transcript, aggregate idea database, per-idea JSON, Markdown, thumbnails, Mermaid source, and static SVG artifacts. |

### Agentic behavior

- New idea IDs run the complete enrichment pipeline.
- Existing ideas append only their relevant transcript excerpt.
- The decision router always refreshes the summary and selects only downstream sections affected by new discussion.
- Different ideas are processed concurrently; updates for the same idea remain FIFO.
- Stable chunk IDs, transcript segments, and worker offsets prevent repeated processing.
- Competitor research uses grounded search and stores its source URLs.
- The frontend displays backend-generated static SVG workflow and architecture diagrams; browser-side interactive maps are intentionally disabled.

## Run the complete live demo locally

### Prerequisites

- Python 3.13 and [`uv`](https://docs.astral.sh/uv/)
- Node.js 22
- A browser with microphone permission
- Gradium and Gemini API keys

Create `.env` in the repository root:

```dotenv
GRADIUM_API_KEY=your_gradium_api_key
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-3.8-flash
```

Never commit `.env`; it is ignored by Git.

Install shared Python and frontend dependencies once:

```bash
pip install -r requirements.txt
cd frontend && npm ci && cd ..
```

Run each block in a separate Git Bash terminal from the repository root.

### 1. Transcription server

Port `8010` avoids conflicts with software commonly using port `8000`:

```bash
cd /c/agentic_hackaton_zurich/tech-europe-agentic-hack/backend/transcriber
TRANSCRIBER_PORT=8010 uv run python main.py
```

### 2. Gemini enrichment API

```bash
cd /c/agentic_hackaton_zurich/tech-europe-agentic-hack
python -m uvicorn backend.enrichment.main:app --host 127.0.0.1 --port 8001 --reload
```

### 3. Gemini idea classifier

```bash
cd /c/agentic_hackaton_zurich/tech-europe-agentic-hack/backend/engine
uv run python main.py
```

### 4. Automatic enrichment router

```bash
cd /c/agentic_hackaton_zurich/tech-europe-agentic-hack
python -m backend.enrichment.classified_chunks_worker \
  --file pubsub/classified-chunks.jsonl \
  --interval 1
```

### 5. Frontend

```bash
cd /c/agentic_hackaton_zurich/tech-europe-agentic-hack/frontend
TRANSCRIBER_TARGET=http://127.0.0.1:8010 \
VITE_ENRICHMENT_URL=http://127.0.0.1:8001 \
npm run dev
```

Open **[http://127.0.0.1:5173](http://127.0.0.1:5173)** and allow microphone access.

## Try a brainstorming session

1. Click **Start** and speak about an idea for at least 15–20 seconds.
2. Include what it does, how it works, potential benefits, concerns, competitors, and unresolved questions.
3. Click **Stop** and wait for **Saving…** to finish.
4. The engine processes approximately 500-character chunks, with a ten-second idle flush for smaller remainders.
5. Allow roughly 30–90 seconds for the full new-idea pipeline. The idea card updates automatically without a browser refresh.
6. Open the card to inspect its summary, pros and cons, open questions, competitors, workflow, architecture, and complete JSON.

The prototype has one shared recording room and supports one active recording at a time.

## Health checks

```bash
# Local services
curl http://127.0.0.1:8010/health
curl http://127.0.0.1:8001/health

# Same transcription route used by the browser
curl http://127.0.0.1:5173/api/transcriber/transcript

# Real Gemini request
python -m backend.enrichment.ping_models --provider gemini
curl -sS "http://127.0.0.1:8001/models/ping?provider=gemini" | python -m json.tool
```

## Test one complete enrichment directly

```bash
curl -sS -X POST \
  http://127.0.0.1:8001/ideas/idea_pr_bot_01/enrich \
  -H 'content-type: application/json' \
  -d '{}' \
  | python -m json.tool
```

This makes real Gemini and grounded-search calls and may take 30–90 seconds.

## Data and artifacts

```text
data/
├── transcript.txt
├── ideas.json
└── ideas/
    └── <idea-id>/
        ├── idea.json
        ├── raw-body.txt
        ├── transcript-segments.json
        ├── summary.md
        ├── pros-cons.json
        ├── assumptions-open-questions.md
        ├── competitors.json
        ├── workflow.json
        ├── workflow.svg
        ├── system-architecture.json
        ├── system-architecture.svg
        └── thumbnail.svg
```

The aggregate database is `data/ideas.json`. Every completed save also materializes a frontend-ready per-idea record and artifact folder.

## Verification

```bash
cd frontend
npm run lint
npm run build
node --test src/ideaWorkspace.test.mjs

cd ..
python -m unittest discover -s backend/enrichment -p "test_*.py"

cd backend/engine
uv run python -m unittest test_focus -v
```

## Contributors

- [Marko Haralović](https://github.com/MarkoHaralovic)
- [Leonarda Lovrić](https://github.com/leonarda4)
- [Giacomo Cirò](https://github.com/giacomo-ciro)
- [Alex John Caldarone](https://github.com/alexcaldarone)

# Idea enrichment backend

This service reads one selected idea from `data/ideas.json` and runs:

```text
messy multi-person transcript
  -> summary
  -> pros/cons (from the transcript)
  -> Mermaid workflow/design (from the summary)
  -> online competitor research (from the summary)
  -> atomic update of the same idea
```

## Bash setup

Run these commands from the repository root. In Git Bash on Windows:

```bash
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -r backend/enrichment/requirements.txt
cp .env.example .env
```

On Linux/macOS, activate with `source .venv/bin/activate` instead. Add a real
`GEMINI_API_KEY` or `OPENAI_API_KEY` to `.env`. `DEFAULT_PROVIDER=auto` prefers
Gemini and falls back to OpenAI. `DEFAULT_PROVIDER=mock` runs the pipeline
offline, but competitor results are then demo data rather than live research.

## Ping the models

These commands make a real minimal inference call and exit non-zero if the key,
model, or network is invalid. They never fall back to mock data.

```bash
python -m backend.enrichment.ping_models --provider gemini
python -m backend.enrichment.ping_models --provider openai
```

Only run the command for the provider you configured. To require both:

```bash
python -m backend.enrichment.ping_models --provider all
```

## Run and test the API

```bash
uvicorn backend.enrichment.main:app --host 0.0.0.0 --port 8001 --reload
```

In a second Bash terminal:

```bash
curl -s http://localhost:8001/health
curl -s 'http://localhost:8001/models/ping?provider=gemini'
```

An idea record needs an `id`, `title`, and its current full `transcript`:

```json
{
  "id": "solar-kiosk",
  "title": "Solar repair kiosk",
  "transcript": "Maya: Commuters need quick repairs. Jon: Solar lowers costs. Lee: Theft is a risk."
}
```

Upsert and enrich that selected idea:

```bash
curl -s -X POST http://localhost:8001/ideas \
  -H 'content-type: application/json' \
  -d '{"id":"solar-kiosk","title":"Solar repair kiosk","transcript":"Maya: Commuters need quick repairs. Jon: Solar lowers costs. Lee: Theft is a risk."}'

curl -s -X POST http://localhost:8001/ideas/solar-kiosk/enrich \
  -H 'content-type: application/json' \
  -d '{}'
```

The enrichment call is synchronous and returns the completed idea. It also
persists `summary`, `pros_cons`, `workflow`, `competitors`, and status back to
`data/ideas.json`. Run the offline verification with:

```bash
python -m unittest backend.enrichment.test_pipeline
```

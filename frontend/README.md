# Brainy Storm frontend

React + TypeScript + Vite. Use Node 22.

```bash
npm ci
npm run dev
```

Open http://localhost:5173. Run the transcriber on port 8000, the Node enrichment API on port 3000, and the engine alongside them (see the root README), or start the complete Docker stack with `docker compose up --build` from the repository root.

The browser captures the microphone after **Start**. **Stop** releases it and stays in **Saving…** until the server confirms the final file write. **Reset transcript** is available only while stopped and preserves generated ideas. All speech is labelled **Room**. Export downloads the persisted plain-text transcript.

Vite proxies `/api/transcriber/*` to port 8000 and `/api/enrichment/*` to port 3000's `/api/*` routes. Compose runs this same Vite server, sets the backend targets to Docker service names, and mounts the frontend source for immediate reloads. Dependencies stay in a container volume and are synchronized from the lockfile on startup. The frontend polls ideas every three seconds. Optional API-base overrides: `VITE_TRANSCRIBER_URL`, `VITE_ENRICHMENT_URL`.

The prototype has one shared room. Other sidebar sessions and local card controls remain UI examples. Enrichment is available through the Node API but is not triggered by this UI.

```bash
npm run build
npm run lint
```

import asyncio
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional, Dict, Any

from .config import (
    DEFAULT_PROVIDER,
    GEMINI_MODEL,
    OPENAI_MODEL,
    SERVER_HOST,
    SERVER_PORT,
)
from .models import (
    Idea,
    AutoEnrichRequest,
    ManualEnrichRequest,
    IdeaCreateUpdateRequest,
    TranscriptEnrichRequest,
)
from .storage import storage
from .orchestrator import orchestrator
from .llm_client import llm_client

app = FastAPI(
    title="Brainstorming Agentic Enrichment Microservice",
    description="Asynchronous agentic tool calling for real-time brainstorming sessions.",
    version="1.0.0"
)

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Active WebSocket connections for live UI push
active_websockets: List[WebSocket] = []


async def broadcast_ws(event_dict: Dict[str, Any]):
    disconnected = []
    for ws in active_websockets:
        try:
            await ws.send_json(event_dict)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        if ws in active_websockets:
            active_websockets.remove(ws)


# Subscribe orchestrator events to WebSocket broadcast
orchestrator.subscribe(broadcast_ws)


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "enrichment",
        "default_provider": DEFAULT_PROVIDER,
        "models": {"gemini": GEMINI_MODEL, "openai": OPENAI_MODEL},
        "model_ping": "/models/ping?provider=all",
    }


@app.get("/models/ping")
async def ping_models(provider: str = "all"):
    """Perform a minimal live inference request; never substitutes mock data."""
    try:
        return await llm_client.ping_models(provider)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/ideas", response_model=List[Idea])
async def list_ideas():
    return await storage.get_all_ideas()


@app.get("/ideas/{identifier}", response_model=Idea)
async def get_idea(identifier: str):
    idea = await storage.get_idea(identifier)
    if not idea:
        raise HTTPException(status_code=404, detail=f"Idea '{identifier}' not found.")
    return idea


@app.post("/ideas", response_model=Idea)
async def create_or_update_idea(payload: IdeaCreateUpdateRequest):
    existing = None
    if payload.id:
        existing = await storage.get_idea(payload.id)
    if not existing and payload.title:
        existing = await storage.get_idea(payload.title)

    if existing:
        existing.title = payload.title
        if payload.summary is not None:
            existing.summary = payload.summary
        if payload.transcript is not None:
            existing.transcript = payload.transcript
        if payload.proponents:
            existing.proponents = payload.proponents
        if payload.opponents:
            existing.opponents = payload.opponents
        if payload.thumbnail:
            existing.thumbnail = payload.thumbnail
        saved = await storage.save_or_update_idea(existing)
        return saved
    else:
        new_idea = Idea(
            id=payload.id or payload.title.lower().replace(" ", "-"),
            title=payload.title,
            summary=payload.summary or "",
            transcript=payload.transcript,
            proponents=payload.proponents,
            opponents=payload.opponents,
            thumbnail=payload.thumbnail
        )
        saved = await storage.save_or_update_idea(new_idea)
        return saved


@app.post("/ideas/{identifier}/enrich")
async def enrich_selected_idea(
    identifier: str,
    payload: Optional[TranscriptEnrichRequest] = None,
):
    """Enrich one idea from its stored messy multi-person transcript."""
    try:
        return await orchestrator.enrich_idea_from_transcript(
            identifier=identifier,
            transcript_override=payload.transcript if payload else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/enrich/auto")
async def auto_enrich(req: AutoEnrichRequest):
    """Automatically triage context delta from speech transcriber and call agents if needed."""
    identifier = req.idea_id or req.title
    if not identifier:
        raise HTTPException(status_code=400, detail="Must provide idea_id or title.")
    try:
        result = await orchestrator.auto_evaluate_and_dispatch(
            identifier=identifier,
            context_delta=req.context,
            run_in_background=True
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/enrich/manual")
async def manual_enrich(req: ManualEnrichRequest):
    """Enable the user to explicitly call a service (competitors, workflow, pros_cons, or all)."""
    identifier = req.idea_id or req.title
    if not identifier:
        raise HTTPException(status_code=400, detail="Must provide idea_id or title.")
    try:
        result = await orchestrator.manual_dispatch(
            identifier=identifier,
            service=req.service,
            context=req.context,
            run_in_background=True
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_websockets.append(websocket)
    try:
        while True:
            # Keep alive; client can send pings
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in active_websockets:
            active_websockets.remove(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.enrichment.main:app", host=SERVER_HOST, port=SERVER_PORT, reload=True)

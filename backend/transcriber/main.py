import os
import logging
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import gradium

from batching import TranscriptStore, parse_batch_seconds
from session import transcribe_session

logger = logging.getLogger("uvicorn.error")

# Load environment variables from local .env or parent .env
LOCAL_ENV = Path(__file__).parent / ".env"
ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=LOCAL_ENV)
load_dotenv(dotenv_path=ROOT_ENV)


def get_gradium_api_key() -> str:
    # Reload in case .env was edited while the server was running
    load_dotenv(dotenv_path=LOCAL_ENV, override=True)
    load_dotenv(dotenv_path=ROOT_ENV, override=True)
    return os.getenv("GRADIUM_API_KEY", "").strip()


HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# Target transcript file: data/transcript.txt in project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
TRANSCRIPT_FILE = DATA_DIR / "transcript.txt"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.batch_seconds = parse_batch_seconds(os.getenv("TRANSCRIPT_BATCH_SECONDS"))
    store = TranscriptStore(TRANSCRIPT_FILE)
    await store.initialize()
    app.state.transcript_store = store
    yield


app = FastAPI(
    title="Transcriber Service",
    description="Real-time Speech-to-Text WebSocket service powered by Gradium",
    version="0.1.0",
    lifespan=lifespan,
)

# Enable CORS for future frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    api_key = get_gradium_api_key()
    return {
        "service": "transcriber",
        "status": "running",
        "websocket_endpoint": "/ws/transcribe",
        "api_key_configured": bool(api_key and api_key != "your-gradium-api-key-here"),
        "transcript_path": str(TRANSCRIPT_FILE),
    }


@app.get("/health")
async def health_check():
    api_key = get_gradium_api_key()
    is_key_set = bool(api_key and api_key != "your-gradium-api-key-here")
    return {
        "status": "healthy" if is_key_set else "needs_api_key",
        "api_key_configured": is_key_set,
        "transcript_file": str(TRANSCRIPT_FILE),
    }


@app.get("/transcript")
async def get_transcript(request: Request):
    """Returns the full text currently saved in data/transcript.txt"""
    content = await request.app.state.transcript_store.read()
    return {"transcript": content}


@app.post("/transcript/clear")
async def clear_transcript(request: Request):
    """Clears data/transcript.txt for a new brainstorming session"""
    if not await request.app.state.transcript_store.clear():
        raise HTTPException(
            status_code=409,
            detail="Stop all recordings and wait for them to finish before clearing the transcript",
        )
    return {"status": "cleared", "message": "Transcript file reset successfully"}


@app.websocket("/ws/transcribe")
async def websocket_transcribe(ws: WebSocket):
    await ws.accept()

    api_key = get_gradium_api_key()
    # Verify API key
    if not api_key or api_key == "your-gradium-api-key-here":
        err_msg = "GRADIUM_API_KEY is missing. Please set it in backend/transcriber/.env"
        await ws.send_json({"type": "error", "message": err_msg})
        await ws.close(code=1008)
        return

    store = ws.app.state.transcript_store
    close_code = 1011
    try:
        # Registration covers provider initialization, draining, and the final save.
        async with store.session():
            client = gradium.GradiumClient(api_key=api_key)
            stt = client.stt_realtime(
                model_name="default",
                input_format="pcm",
                json_config={"language": "en"},
                wait_for_ready_on_start=True,
            )
            async with AsyncExitStack() as stack:
                # Gradium 0.6.4 can leave its HTTP session open if __aenter__
                # fails. Register cleanup before connecting, including setup errors.
                stack.push_async_exit(stt)
                await stt.__aenter__()
                await transcribe_session(ws, stt, store, ws.app.state.batch_seconds)
        close_code = 1000
    except Exception as exc:
        logger.exception("Transcription session failed")
        try:
            await ws.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass
    finally:
        try:
            await ws.close(code=close_code)
        except Exception:
            pass  # The client may already have disconnected.


if __name__ == "__main__":
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)

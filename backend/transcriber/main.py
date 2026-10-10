import os
import json
import asyncio
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import gradium

# Load environment variables from local .env or parent .env
LOCAL_ENV = Path(__file__).parent / ".env"
ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=LOCAL_ENV)
load_dotenv(dotenv_path=ROOT_ENV)

GRADIUM_API_KEY = os.getenv("GRADIUM_API_KEY", "").strip()
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# Target transcript file: data/transcript.txt in project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
TRANSCRIPT_FILE = DATA_DIR / "transcript.txt"

# Ensure data directory and transcript file exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
if not TRANSCRIPT_FILE.exists():
    TRANSCRIPT_FILE.touch()

app = FastAPI(
    title="Transcriber Service",
    description="Real-time Speech-to-Text WebSocket service powered by Gradium",
    version="0.1.0",
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
    return {
        "service": "transcriber",
        "status": "running",
        "websocket_endpoint": "/ws/transcribe",
        "api_key_configured": bool(GRADIUM_API_KEY and GRADIUM_API_KEY != "your-gradium-api-key-here"),
        "transcript_path": str(TRANSCRIPT_FILE),
    }


@app.get("/health")
async def health_check():
    is_key_set = bool(GRADIUM_API_KEY and GRADIUM_API_KEY != "your-gradium-api-key-here")
    return {
        "status": "healthy" if is_key_set else "needs_api_key",
        "api_key_configured": is_key_set,
        "transcript_file": str(TRANSCRIPT_FILE),
    }


@app.get("/transcript")
async def get_transcript():
    """Returns the full text currently saved in data/transcript.txt"""
    if not TRANSCRIPT_FILE.exists():
        return {"transcript": ""}
    content = TRANSCRIPT_FILE.read_text(encoding="utf-8")
    return {"transcript": content}


@app.post("/transcript/clear")
async def clear_transcript():
    """Clears data/transcript.txt for a new brainstorming session"""
    TRANSCRIPT_FILE.write_text("", encoding="utf-8")
    return {"status": "cleared", "message": "Transcript file reset successfully"}


@app.websocket("/ws/transcribe")
async def websocket_transcribe(ws: WebSocket):
    await ws.accept()

    # Verify API key
    if not GRADIUM_API_KEY or GRADIUM_API_KEY == "your-gradium-api-key-here":
        err_msg = "GRADIUM_API_KEY is missing. Please set it in backend/transcriber/.env"
        await ws.send_json({"type": "error", "message": err_msg})
        await ws.close(code=1008)
        return

    print("🔌 Client connected to /ws/transcribe. Initializing Gradium STT...")

    try:
        client = gradium.GradiumClient(api_key=GRADIUM_API_KEY)
        
        # Connect to Gradium real-time STT WebSocket
        async with client.stt_realtime(
            model_name="default",
            input_format="pcm",
            json_config={"language": "en"}
        ) as stt:
            print(" Connected to Gradium STT WebSocket. Ready for audio.")
            await ws.send_json({"type": "ready", "message": "Ready to receive audio stream"})

            # Producer Task: Read audio chunks from Frontend WebSocket and forward to Gradium
            async def receive_from_client():
                try:
                    while True:
                        msg = await ws.receive()
                        
                        # Handle raw binary audio frames (PCM bytes)
                        if "bytes" in msg and msg["bytes"]:
                            await stt.send_audio(msg["bytes"])

                        # Handle text / control commands (JSON)
                        elif "text" in msg and msg["text"]:
                            try:
                                payload = json.loads(msg["text"])
                                action = payload.get("action")
                                if action == "stop":
                                    print("🛑 Received stop signal from client.")
                                    await stt.send_eos()
                                    break
                                elif action == "flush":
                                    await stt.send_flush()
                            except json.JSONDecodeError:
                                pass
                except WebSocketDisconnect:
                    print("⚠️ Client disconnected from WebSocket.")
                except Exception as e:
                    print(f"Error receiving from client: {e}")
                finally:
                    try:
                        await stt.send_eos()
                    except Exception:
                        pass

            # Consumer Task: Read transcript segments from Gradium and write to disk
            async def process_gradium_transcripts():
                try:
                    async for msg in stt:
                        msg_type = msg.get("type")
                        
                        if msg_type == "text":
                            text = msg.get("text", "").strip()
                            if text:
                                timestamp = datetime.now().strftime("%H:%M:%S")
                                print(f"📝 [{timestamp}] Transcribed: {text}")
                                
                                # Write periodically to data/transcript.txt
                                with open(TRANSCRIPT_FILE, "a", encoding="utf-8") as f:
                                    f.write(f"[{timestamp}] {text}\n")
                                    f.flush()
                                
                                # Broadcast back to frontend for live UI captions
                                await ws.send_json({
                                    "type": "transcript",
                                    "text": text,
                                    "timestamp": timestamp,
                                })
                        elif msg_type == "error":
                            print(f"❌ Gradium error: {msg}")
                            await ws.send_json({"type": "error", "error": msg})
                except Exception as e:
                    print(f"Error processing transcripts: {e}")

            # Run both tasks concurrently
            await asyncio.gather(receive_from_client(), process_gradium_transcripts())

    except Exception as e:
        print(f"❌ Gradium STT session error: {e}")
        try:
            await ws.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        print("🔌 Session ended.")


if __name__ == "__main__":
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)

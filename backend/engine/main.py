import json
import logging
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel

from prompt import build_prompt


REPO_ROOT = Path(__file__).resolve().parents[2]

logger = logging.getLogger("engine")


class LevelColorFormatter(logging.Formatter):
    COLORS = {logging.WARNING: "\033[33m", logging.ERROR: "\033[31m"}
    DIM = "\033[2m"
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        timestamp = self.formatTime(record, "%H:%M:%S")
        color = self.COLORS.get(record.levelno, "")
        return f"{self.DIM}{timestamp}{self.RESET}  {color}{record.getMessage()}{self.RESET}"


def setup_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(LevelColorFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    # Silence per-request lines from the HTTP client and the Gemini SDK.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("google_genai").setLevel(logging.WARNING)


def plural(count: int, noun: str) -> str:
    return f"{count:,} {noun}" if count == 1 else f"{count:,} {noun}s"


class IdeaUpdate(BaseModel):
    id: int | None
    title: str
    summary: str


class ChunkIdeas(BaseModel):
    ideas: list[IdeaUpdate]


def init_ideas(ideas_path: Path) -> None:
    ideas_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with ideas_path.open("x", encoding="utf-8") as output:
            json.dump({"ideas": []}, output)
    except FileExistsError:
        pass


def load_ideas(ideas_path: Path) -> list[dict]:
    return json.loads(ideas_path.read_text())["ideas"]


def save_ideas(ideas: list[dict], ideas_path: Path) -> None:
    # Write to a temp file and rename, so readers never see a half-written file.
    tmp_path = ideas_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps({"ideas": ideas}, indent=4, ensure_ascii=False))
    os.replace(tmp_path, ideas_path)


def file_identity(path: Path) -> tuple[int, int]:
    stat = path.stat()
    return stat.st_dev, stat.st_ino


def read_transcript(path: Path) -> tuple[tuple[int, int], str]:
    # Read identity from the open file so a concurrent Reset cannot mix generations.
    with path.open(encoding="utf-8", errors="replace") as source:
        stat = os.fstat(source.fileno())
        text = source.read()
    # Direct file readers must wait for a complete newline-terminated batch.
    return (stat.st_dev, stat.st_ino), text[:text.rfind("\n") + 1]


def cut_chunk(pending: str, chunk_chars: int) -> str | None:
    if len(pending) < chunk_chars:
        return None

    # Cut back to the last whitespace so words are not split across chunks.
    chunk = pending[:chunk_chars]
    last_space = max(chunk.rfind(" "), chunk.rfind("\n"))
    if last_space > 0:
        chunk = chunk[: last_space + 1]
    return chunk


def extract_ideas(
    client: genai.Client,
    model: str,
    ideas: list[dict],
    chunk: str,
    max_retries: int,
) -> list[IdeaUpdate]:
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=ChunkIdeas,
    )
    prompt = build_prompt(ideas, chunk)
    logger.info("  → request · %s · %s", plural(len(ideas), "known idea"), plural(len(prompt), "prompt char"))

    start = time.monotonic()
    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(model=model, contents=prompt, config=config)
            updates = ChunkIdeas.model_validate_json(response.text).ideas
            logger.info("  ← response · %.1fs · %s", time.monotonic() - start, plural(len(updates), "idea"))
            return updates
        except Exception as error:
            logger.warning("  ! attempt %d/%d failed · %s: %s", attempt, max_retries, type(error).__name__, error)
    raise RuntimeError(f"Gemini failed after {max_retries} attempts")


def merge_ideas(ideas: list[dict], updates: list[IdeaUpdate]) -> list[dict]:
    ideas_by_id = {idea["id"]: idea for idea in ideas}
    next_id = max(ideas_by_id, default=0) + 1

    for update in updates:
        if update.id in ideas_by_id:
            ideas_by_id[update.id]["title"] = update.title
            ideas_by_id[update.id]["summary"] = update.summary
            logger.info("  ~ #%d %s", update.id, update.title)
        else:
            # Unknown ids are treated as new ideas.
            ideas_by_id[next_id] = {"id": next_id, "title": update.title, "summary": update.summary}
            logger.info("  + #%d %s", next_id, update.title)
            next_id += 1

    return list(ideas_by_id.values())


def main(
    transcript_path: Path,
    ideas_path: Path,
    model: str,
    chunk_chars: int,
    poll_interval_s: float,
    max_retries: int,
    request_timeout_s: float,
) -> None:
    load_dotenv(REPO_ROOT / ".env")
    model = os.getenv("GEMINI_MODEL") or model
    client = genai.Client(
        api_key=os.environ["GEMINI_API_KEY"],
        http_options=types.HttpOptions(timeout=int(request_timeout_s * 1000)),
    )
    logger.info(
        "engine started · model %s · chunk %d chars · poll %.1fs · retries %d · timeout %gs",
        model, chunk_chars, poll_interval_s, max_retries, request_timeout_s,
    )
    init_ideas(ideas_path)
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.touch(exist_ok=True)
    logger.info("using existing ideas in %s", ideas_path)

    offset = 0
    identity = None
    previous_length = 0
    last_text_at = time.monotonic()
    chunk_number = 1
    last_waiting_chars = None
    while True:
        time.sleep(poll_interval_s)
        try:
            current_identity, text = read_transcript(transcript_path)
            if current_identity != identity:
                identity = current_identity
                offset = 0
                previous_length = 0
                last_text_at = time.monotonic()
                logger.info("transcript replaced · reading from the beginning")
            if len(text) != previous_length:
                previous_length = len(text)
                last_text_at = time.monotonic()
            pending = text[offset:]
            chunk = cut_chunk(pending, chunk_chars)
            if chunk is None and pending and time.monotonic() - last_text_at >= 10:
                chunk = pending
            if chunk is None:
                # Log only when the pending count changes, to keep idle ticks quiet.
                if len(pending) != last_waiting_chars:
                    logger.info("waiting · %d/%d new chars", len(pending), chunk_chars)
                    last_waiting_chars = len(pending)
                continue
            last_waiting_chars = None

            logger.info(
                "chunk #%d · %s · offset %s → %s",
                chunk_number, plural(len(chunk), "char"), f"{offset:,}", f"{offset + len(chunk):,}",
            )
            updates = extract_ideas(client, model, load_ideas(ideas_path), chunk, max_retries)

            # Re-read right before writing to keep edits made by enrichment during the API call.
            merged_ideas = merge_ideas(load_ideas(ideas_path), updates)
            if file_identity(transcript_path) != identity:
                logger.info("discarded response · source transcript was reset")
                continue
            save_ideas(merged_ideas, ideas_path)
            logger.info("  saved · %s total", plural(len(merged_ideas), "idea"))

            offset += len(chunk)
            chunk_number += 1
        except Exception as error:
            logger.error("  ✗ tick failed, retrying chunk #%d next tick · %s: %s", chunk_number, type(error).__name__, error)


if __name__ == "__main__":
    TRANSCRIPT_PATH = REPO_ROOT / "data" / "transcript.txt"
    IDEAS_PATH = REPO_ROOT / "data" / "ideas.json"
    MODEL = "gemini-3.8-flash"
    CHUNK_CHARS = 500  # Characters consumed per Gemini call.
    POLL_INTERVAL_S = 3.0
    MAX_RETRIES = 3  # Attempts per Gemini call before giving up on the tick.
    REQUEST_TIMEOUT_S = 30.0

    setup_logging()
    main(
        transcript_path=TRANSCRIPT_PATH,
        ideas_path=IDEAS_PATH,
        model=MODEL,
        chunk_chars=CHUNK_CHARS,
        poll_interval_s=POLL_INTERVAL_S,
        max_retries=MAX_RETRIES,
        request_timeout_s=REQUEST_TIMEOUT_S,
    )

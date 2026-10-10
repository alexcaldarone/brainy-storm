import hashlib
import json
import logging
import os
import re
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
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("google_genai").setLevel(logging.WARNING)


def plural(count: int, noun: str) -> str:
    return f"{count:,} {noun}" if count == 1 else f"{count:,} {noun}s"


class IdeaUpdate(BaseModel):
    id: str | None
    title: str
    summary: str
    is_currently_discussed: bool = False


class ChunkIdeas(BaseModel):
    ideas: list[IdeaUpdate]


def reset_topic(topic_path: Path) -> None:
    topic_path.parent.mkdir(parents=True, exist_ok=True)
    topic_path.write_text("", encoding="utf-8")


def publish(topic_path: Path, messages: list[dict]) -> None:
    if not messages:
        return
    payload = "".join(json.dumps(message, ensure_ascii=False) + "\n" for message in messages)
    fd = os.open(topic_path, os.O_WRONLY | os.O_APPEND | os.O_CREAT)
    try:
        os.write(fd, payload.encode("utf-8"))
    finally:
        os.close(fd)


def load_known_ideas(ideas_path: Path) -> dict[str, dict]:
    try:
        payload = json.loads(ideas_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    raw_ideas = payload.get("ideas", []) if isinstance(payload, dict) else payload
    if not isinstance(raw_ideas, list):
        return {}
    known: dict[str, dict] = {}
    for item in raw_ideas:
        if not isinstance(item, dict) or not item.get("id") or not item.get("title"):
            continue
        known[str(item["id"])] = {
            "title": str(item["title"]),
            "summary": str(item.get("summary") or item.get("short_summary") or ""),
        }
    return known


def merge_ideas(ideas: list[dict], updates: list[IdeaUpdate]) -> list[dict]:
    """Merge classifier output for focused unit tests and lightweight consumers."""
    merged = [{**idea, "is_currently_discussed": False} for idea in ideas]
    by_id = {str(idea.get("id")): index for index, idea in enumerate(merged)}
    focus_index: int | None = None
    for update in updates:
        index = by_id.get(str(update.id)) if update.id is not None else None
        if index is None:
            index = len(merged)
            new_id: str | int = update.id if update.id is not None else index
            merged.append({"id": new_id})
            by_id[str(new_id)] = index
        merged[index].update(
            title=update.title,
            summary=update.summary,
            is_currently_discussed=False,
        )
        if update.is_currently_discussed:
            focus_index = index
    if focus_index is not None:
        merged[focus_index]["is_currently_discussed"] = True
    return merged


def stable_idea_id(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")[:42] or "idea"
    digest = hashlib.sha256(title.strip().lower().encode("utf-8")).hexdigest()[:8]
    return f"idea_{slug}_{digest}"


def resolve_updates(
    known_ideas: dict[str, dict], updates: list[IdeaUpdate]
) -> tuple[dict[str, dict], list[dict]]:
    next_known = dict(known_ideas)
    references: list[dict] = []
    for update in updates:
        idea_id = update.id if update.id in next_known else stable_idea_id(update.title)
        next_known[idea_id] = {"title": update.title, "summary": update.summary}
        references.append(
            {
                "id": idea_id,
                "title": update.title,
                "short-summary": update.summary,
                "is_currently_discussed": update.is_currently_discussed,
            }
        )
    return next_known, references


def file_identity(path: Path) -> tuple[int, int]:
    stat = path.stat()
    return stat.st_dev, stat.st_ino


def read_transcript(path: Path) -> tuple[tuple[int, int], str]:
    with path.open(encoding="utf-8", errors="replace") as source:
        stat = os.fstat(source.fileno())
        text = source.read()
    newline = text.rfind("\n")
    return (stat.st_dev, stat.st_ino), text[: newline + 1] if newline >= 0 else ""


def cut_chunk(pending: str, chunk_chars: int) -> str | None:
    if len(pending) < chunk_chars:
        return None
    chunk = pending[:chunk_chars]
    last_space = max(chunk.rfind(" "), chunk.rfind("\n"))
    return chunk[: last_space + 1] if last_space > 0 else chunk


def extract_ideas(
    client: genai.Client,
    model: str,
    ideas: dict[str, dict],
    chunk: str,
    max_retries: int,
) -> list[IdeaUpdate]:
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=ChunkIdeas,
    )
    prompt = build_prompt(ideas, chunk)
    logger.info("  -> request · %s · %s", plural(len(ideas), "known idea"), plural(len(prompt), "prompt char"))
    started = time.monotonic()
    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(model=model, contents=prompt, config=config)
            updates = ChunkIdeas.model_validate_json(response.text).ideas
            logger.info("  <- response · %.1fs · %s", time.monotonic() - started, plural(len(updates), "idea"))
            return updates
        except Exception as error:
            logger.warning("  ! attempt %d/%d failed · %s: %s", attempt, max_retries, type(error).__name__, error)
    raise RuntimeError(f"Gemini failed after {max_retries} attempts")


def run(
    transcript_path: Path,
    ideas_path: Path,
    idea_updates_path: Path,
    classified_chunks_path: Path,
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
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.touch(exist_ok=True)
    logger.info("engine started · model %s · source %s", model, transcript_path)

    def start_session() -> dict[str, dict]:
        for topic_path in (idea_updates_path, classified_chunks_path):
            reset_topic(topic_path)
            logger.info("reset %s", topic_path.relative_to(REPO_ROOT))
        return load_known_ideas(ideas_path)

    known_ideas = start_session()
    offset = 0
    identity: tuple[int, int] | None = None
    previous_length = 0
    last_text_at = time.monotonic()
    chunk_number = 1
    last_waiting_chars: int | None = None

    while True:
        time.sleep(poll_interval_s)
        try:
            current_identity, transcript = read_transcript(transcript_path)
            if current_identity != identity or len(transcript) < offset:
                if identity is not None:
                    logger.info("transcript replaced or reset · starting a new session")
                    known_ideas = start_session()
                identity = current_identity
                offset = 0
                previous_length = 0
                last_text_at = time.monotonic()
                chunk_number = 1

            if len(transcript) != previous_length:
                previous_length = len(transcript)
                last_text_at = time.monotonic()
            pending = transcript[offset:]
            chunk = cut_chunk(pending, chunk_chars)
            if chunk is None and pending and time.monotonic() - last_text_at >= 10:
                chunk = pending
            if chunk is None:
                if len(pending) != last_waiting_chars:
                    logger.info("waiting · %d/%d new chars", len(pending), chunk_chars)
                    last_waiting_chars = len(pending)
                continue

            last_waiting_chars = None
            logger.info("chunk #%d · %s · offset %d -> %d", chunk_number, plural(len(chunk), "char"), offset, offset + len(chunk))
            updates = extract_ideas(client, model, known_ideas, chunk, max_retries)
            known_ideas, references = resolve_updates(known_ideas, updates)

            if file_identity(transcript_path) != identity:
                logger.info("discarded response · source transcript was reset")
                continue

            chunk_seed = f"{identity[0]}:{identity[1]}:{offset}:".encode("utf-8") + chunk.encode("utf-8")
            chunk_id = hashlib.sha256(chunk_seed).hexdigest()[:20]
            publish(idea_updates_path, references)
            publish(
                classified_chunks_path,
                [{"chunk_id": chunk_id, "chunk": chunk, "ideas": references}],
            )
            logger.info("  published · %s · %s", chunk_id, plural(len(references), "idea"))
            offset += len(chunk)
            chunk_number += 1
        except Exception as error:
            logger.error("  x tick failed, retrying chunk #%d · %s: %s", chunk_number, type(error).__name__, error)


if __name__ == "__main__":
    setup_logging()
    run(
        transcript_path=REPO_ROOT / "data" / "transcript.txt",
        ideas_path=REPO_ROOT / "data" / "ideas.json",
        idea_updates_path=REPO_ROOT / "pubsub" / "idea-updates.jsonl",
        classified_chunks_path=REPO_ROOT / "pubsub" / "classified-chunks.jsonl",
        model="gemini-3.8-flash",
        chunk_chars=500,
        poll_interval_s=3.0,
        max_retries=3,
        request_timeout_s=30.0,
    )

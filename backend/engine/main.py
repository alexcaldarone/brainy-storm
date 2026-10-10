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
    id: str | None
    title: str
    summary: str
    is_currently_discussed: bool = False


class ChunkIdeas(BaseModel):
    ideas: list[IdeaUpdate]


def reset_topic(topic_path: Path) -> None:
    topic_path.parent.mkdir(parents=True, exist_ok=True)
    topic_path.write_text("")


def publish(topic_path: Path, messages: list[dict]) -> None:
    # One O_APPEND write per call, so concurrent publishers never interleave or lose lines.
    payload = "".join(json.dumps(message, ensure_ascii=False) + "\n" for message in messages)
    fd = os.open(topic_path, os.O_WRONLY | os.O_APPEND | os.O_CREAT)
    try:
        os.write(fd, payload.encode("utf-8"))
    finally:
        os.close(fd)


def to_message(idea_id: str, idea: dict) -> dict:
    return {"id": idea_id, "title": idea["title"], "short-summary": idea["summary"]}


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
    ideas: dict[str, dict],
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


def merge_ideas(ideas: dict[str, dict], updates: list[IdeaUpdate]) -> tuple[dict[str, dict], list[str]]:
    merged = dict(ideas)
    touched_ids = []

    for update in updates:
        if update.id in merged:
            idea_id = update.id
            logger.info("  ~ %s %s", idea_id, update.title)
        else:
            # Unknown ids are treated as new ideas.
            idea_id = f"idea-{len(merged) + 1}"
            logger.info("  + %s %s", idea_id, update.title)
        merged[idea_id] = {"title": update.title, "summary": update.summary}
        if idea_id not in touched_ids:
            touched_ids.append(idea_id)

    return merged, touched_ids


def main(
    transcript_path: Path,
    idea_updates_path: Path,
    classified_chunks_path: Path,
    model: str,
    chunk_chars: int,
    poll_interval_s: float,
    max_retries: int,
    request_timeout_s: float,
) -> None:
    load_dotenv(REPO_ROOT / ".env")
    client = genai.Client(
        api_key=os.environ["GEMINI_API_KEY"],
        http_options=types.HttpOptions(timeout=int(request_timeout_s * 1000)),
    )
    logger.info(
        "engine started · model %s · chunk %d chars · poll %.1fs · retries %d · timeout %gs",
        model, chunk_chars, poll_interval_s, max_retries, request_timeout_s,
    )

    def start_session() -> None:
        # Each session starts fresh: subscribers see the topics shrink and reset themselves.
        for topic_path in (idea_updates_path, classified_chunks_path):
            reset_topic(topic_path)
            logger.info("reset %s", topic_path.relative_to(REPO_ROOT))

    start_session()
    ideas: dict[str, dict] = {}
    offset = 0
    chunk_number = 1
    last_waiting_chars = None
    while True:
        time.sleep(poll_interval_s)
        try:
            transcript = transcript_path.read_text(errors="replace")
            if len(transcript) < offset:
                # The transcriber cleared the transcript: a new recording is a new session.
                logger.info("transcript shrank below offset · starting a new session")
                start_session()
                ideas, offset, chunk_number = {}, 0, 1
            pending = transcript[offset:]
            chunk = cut_chunk(pending, chunk_chars)
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
            updates = extract_ideas(client, model, ideas, chunk, max_retries)
            merged_ideas, touched_ids = merge_ideas(ideas, updates)

            # Publish idea updates first, so the frontend knows an idea before enrichment does.
            publish(idea_updates_path, [to_message(idea_id, merged_ideas[idea_id]) for idea_id in touched_ids])
            publish(
                classified_chunks_path,
                [{"chunk": chunk, "ideas": [to_message(idea_id, merged_ideas[idea_id]) for idea_id in touched_ids]}],
            )
            logger.info("  published · %s touched · %s total", plural(len(touched_ids), "idea"), plural(len(merged_ideas), "idea"))

            ideas = merged_ideas
            offset += len(chunk)
            chunk_number += 1
        except Exception as error:
            logger.error("  ✗ tick failed, retrying chunk #%d next tick · %s: %s", chunk_number, type(error).__name__, error)


if __name__ == "__main__":
    TRANSCRIPT_PATH = REPO_ROOT / "pubsub" / "transcript.txt"
    IDEA_UPDATES_PATH = REPO_ROOT / "pubsub" / "idea-updates.jsonl"
    CLASSIFIED_CHUNKS_PATH = REPO_ROOT / "pubsub" / "classified-chunks.jsonl"
    MODEL = "gemini-3.8-flash"
    CHUNK_CHARS = 500  # Characters consumed per Gemini call.
    POLL_INTERVAL_S = 3.0
    MAX_RETRIES = 3  # Attempts per Gemini call before giving up on the tick.
    REQUEST_TIMEOUT_S = 30.0

    setup_logging()
    main(
        transcript_path=TRANSCRIPT_PATH,
        idea_updates_path=IDEA_UPDATES_PATH,
        classified_chunks_path=CLASSIFIED_CHUNKS_PATH,
        model=MODEL,
        chunk_chars=CHUNK_CHARS,
        poll_interval_s=POLL_INTERVAL_S,
        max_retries=MAX_RETRIES,
        request_timeout_s=REQUEST_TIMEOUT_S,
    )

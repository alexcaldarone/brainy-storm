import json
import asyncio
from pathlib import Path
from typing import List, Optional, Dict, Any
from .config import IDEAS_FILE, TRANSCRIPT_FILE
from .models import Idea

_storage_lock = asyncio.Lock()


class StorageManager:
    """Handles async-safe read/write operations to data/ideas.json and transcript.txt."""

    def __init__(self, ideas_path: Path = IDEAS_FILE, transcript_path: Path = TRANSCRIPT_FILE):
        self.ideas_path = Path(ideas_path)
        self.transcript_path = Path(transcript_path)
        self._ensure_files()

    def _ensure_files(self):
        self.ideas_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.ideas_path.exists():
            with open(self.ideas_path, "w", encoding="utf-8") as f:
                json.dump({"ideas": []}, f, indent=2)
        if not self.transcript_path.exists():
            with open(self.transcript_path, "w", encoding="utf-8") as f:
                f.write("")

    async def get_all_ideas(self) -> List[Idea]:
        async with _storage_lock:
            return self._read_ideas_sync()

    def _read_ideas_sync(self) -> List[Idea]:
        if not self.ideas_path.exists():
            return []
        try:
            with open(self.ideas_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return []
                data = json.loads(content)
        except (json.JSONDecodeError, OSError):
            return []

        raw_list = data.get("ideas", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        ideas = []
        for item in raw_list:
            if isinstance(item, dict):
                # Ensure each idea has an id if missing
                if "id" not in item:
                    item["id"] = item.get("title", "").lower().replace(" ", "-") or "idea-1"
                try:
                    ideas.append(Idea(**item))
                except Exception:
                    # Fallback for minimal data
                    ideas.append(Idea(
                        id=item.get("id", "idea-1"),
                        title=item.get("title", "Untitled"),
                        summary=item.get("summary", ""),
                        thumbnail=item.get("thumbnail")
                    ))
        return ideas

    async def get_idea(self, identifier: str) -> Optional[Idea]:
        ideas = await self.get_all_ideas()
        identifier_lower = identifier.lower().strip()
        for idea in ideas:
            if idea.id.lower() == identifier_lower or idea.title.lower().strip() == identifier_lower:
                return idea
        return None

    async def save_or_update_idea(self, idea: Idea) -> Idea:
        async with _storage_lock:
            ideas = self._read_ideas_sync()
            found = False
            for i, existing in enumerate(ideas):
                if existing.id == idea.id or existing.title.lower() == idea.title.lower():
                    ideas[i] = idea
                    found = True
                    break
            if not found:
                ideas.append(idea)

            self._write_ideas_sync(ideas)
            return idea

    def _write_ideas_sync(self, ideas: List[Idea]):
        data = {
            "ideas": [idea.model_dump(exclude_none=False) for idea in ideas]
        }
        # Atomic write via temporary file
        temp_file = self.ideas_path.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        temp_file.replace(self.ideas_path)

    async def get_transcript(self) -> str:
        if not self.transcript_path.exists():
            return ""
        try:
            with open(self.transcript_path, "r", encoding="utf-8") as f:
                return f.read()
        except OSError:
            return ""

    async def append_transcript(self, text: str):
        async with _storage_lock:
            with open(self.transcript_path, "a", encoding="utf-8") as f:
                f.write(text.strip() + "\n")


storage = StorageManager()


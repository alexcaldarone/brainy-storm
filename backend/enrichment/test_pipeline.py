import tempfile
import unittest
import importlib
from pathlib import Path
from unittest.mock import patch

from backend.enrichment.llm_client import llm_client
from backend.enrichment.models import Idea
from backend.enrichment.orchestrator import AgenticOrchestrator
from backend.enrichment.storage import StorageManager

orchestrator_module = importlib.import_module("backend.enrichment.orchestrator")


class SelectedIdeaPipelineTest(unittest.IsolatedAsyncioTestCase):
    async def test_selected_idea_is_enriched_from_its_transcript(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            test_storage = StorageManager(
                ideas_path=root / "ideas.json",
                transcript_path=root / "transcript.txt",
            )
            await test_storage.save_or_update_idea(Idea(
                id="solar-kiosk",
                title="Solar repair kiosk",
                transcript=(
                    "Maya: Commuters need quick phone repairs. "
                    "Jon: Solar power lowers operating costs. "
                    "Lee: Weather and theft are serious risks."
                ),
            ))

            async def no_search(*_args, **_kwargs):
                return []

            with (
                patch.object(orchestrator_module, "storage", test_storage),
                patch.object(llm_client, "gemini_key", ""),
                patch.object(llm_client, "openai_key", ""),
                patch.object(llm_client, "search_web", no_search),
            ):
                result = await AgenticOrchestrator().enrich_idea_from_transcript("solar-kiosk")

            self.assertEqual(result["status"], "enriched")
            saved = await test_storage.get_idea("solar-kiosk")
            self.assertIsNotNone(saved)
            self.assertTrue(saved.summary)
            self.assertIsNotNone(saved.pros_cons)
            self.assertTrue(saved.workflow and saved.workflow.mermaid_code)
            self.assertIsNotNone(saved.competitors)
            self.assertTrue(saved.transcript.startswith("Maya:"))


if __name__ == "__main__":
    unittest.main()

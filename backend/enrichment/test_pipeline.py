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
llm_client_module = importlib.import_module("backend.enrichment.llm_client")


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
                patch.object(llm_client_module, "DEFAULT_PROVIDER", "mock"),
                patch.object(llm_client, "search_web", no_search),
            ):
                test_orchestrator = AgenticOrchestrator()
                result = await test_orchestrator.enrich_idea_from_transcript("solar-kiosk")
                individual_results = [
                    await test_orchestrator.enrich_one("solar-kiosk", service)
                    for service in ("summary", "pros-cons", "workflow", "competitors")
                ]
                ingest_result = await test_orchestrator.ingest_transcript_delta(
                    "solar-kiosk",
                    "Maya: Add battery storage so the kiosk can operate after sunset.",
                    enrich=False,
                )
                duplicate_result = await test_orchestrator.ingest_transcript_delta(
                    "solar-kiosk",
                    "Maya: Add battery storage so the kiosk can operate after sunset.",
                    enrich=False,
                )

            self.assertEqual(result["status"], "enriched")
            saved = await test_storage.get_idea("solar-kiosk")
            self.assertIsNotNone(saved)
            self.assertTrue(saved.summary)
            self.assertIsNotNone(saved.pros_cons)
            self.assertTrue(saved.workflow and saved.workflow.mermaid_code)
            self.assertIsNotNone(saved.competitors)
            self.assertTrue(all(
                competitor.idea
                and competitor.yearOfFounding
                and competitor.shortBio
                and competitor.howWeDiffer
                for competitor in saved.competitors.competitors
            ))
            self.assertTrue(saved.transcript.startswith("Maya:"))
            self.assertIn("battery storage", saved.raw_body)
            self.assertTrue(all(item["status"] == "success" for item in individual_results))
            self.assertEqual(ingest_result["status"], "ingested")
            self.assertEqual(duplicate_result["status"], "duplicate")


if __name__ == "__main__":
    unittest.main()

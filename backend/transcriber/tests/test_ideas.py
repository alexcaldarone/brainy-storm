import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
import main


class IdeasTests(unittest.TestCase):
    def test_reads_engine_updates(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(main, "DATA_DIR", Path(directory)):
            self.assertEqual(main.get_ideas(), {"ideas": []})
            path = Path(directory) / "ideas.json"
            idea = {"id": 1, "title": "First thought", "summary": "Details"}
            path.write_text(json.dumps({"ideas": [idea]}))
            self.assertEqual(main.get_ideas(), {"ideas": [idea]})
            idea["summary"] = "Updated details"
            path.write_text(json.dumps({"ideas": [idea]}))
            self.assertEqual(main.get_ideas()["ideas"][0]["summary"], "Updated details")

    def test_rejects_invalid_data(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(main, "DATA_DIR", Path(directory)):
            for content in ['{', '{"ideas": null}', '{"ideas": [{}]}']:
                with self.subTest(content=content):
                    (Path(directory) / "ideas.json").write_text(content)
                    with self.assertRaises(HTTPException) as error:
                        main.get_ideas()
                    self.assertEqual(error.exception.status_code, 503)

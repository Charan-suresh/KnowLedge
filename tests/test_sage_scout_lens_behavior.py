import unittest
from unittest.mock import patch

from knowledge.sage import run_session
from knowledge.scout import tag_content
from knowledge.lens import verify_image


class SageScoutLensBehaviorTests(unittest.TestCase):
    def test_scout_falls_back_when_tool_call_missing(self):
        fake_response = {
            "message": {
                "content": "",
                "tool_calls": [],
            }
        }

        with patch("knowledge.scout.chat", return_value=fake_response):
            concepts = tag_content("bonding present btw two atoms or ions")

        self.assertGreaterEqual(len(concepts), 1)
        self.assertTrue(all(item.concept_tag for item in concepts))

    def test_sage_normalizes_answer_into_single_question(self):
        fake_response = {
            "message": {
                "content": "Assistant:\nCovalent bonds share electrons between atoms.",
                "tool_calls": [],
            }
        }

        with patch("knowledge.sage.chat", return_value=fake_response):
            result = run_session("chemical bonding", [], [{"role": "user", "content": "It shares electrons."}])

        self.assertFalse(result.cleared)
        self.assertTrue(result.response.endswith("?"))
        self.assertNotIn("Assistant:", result.response)

    def test_lens_marks_handwritten_notes_in_response(self):
        fake_response = {
            "message": {
                "content": '{"x": 12, "y": 34, "width": 100, "height": 40, "explanation": "Handwritten notes recognized; no obvious logic failure detected.", "handwritten": true, "has_issue": false, "confidence": 0.94}',
                "audio": None,
            }
        }

        image_bytes = b"fake-image-bytes"
        with patch("knowledge.lens.Image.open") as mock_open, patch("knowledge.lens.chat", return_value=fake_response):
            mock_image = mock_open.return_value
            mock_image.width = 640
            mock_image.height = 480
            result = verify_image(image_bytes, "chemical bonding")

        self.assertTrue(result.handwritten)
        self.assertFalse(result.has_issue)
        self.assertGreater(result.confidence, 0.9)
        self.assertIn("Handwritten notes recognized", result.explanation)


if __name__ == "__main__":
    unittest.main()

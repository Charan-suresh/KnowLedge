import unittest
from unittest.mock import patch

from knowledge.sage import run_session
from knowledge.sage_stream import _enforce_socratic_question
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

    def test_scout_parses_string_tool_arguments(self):
        fake_response = {
            "message": {
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "log_comprehension_concepts",
                            "arguments": '{"concepts": [{"concept_tag": "Recursion", "confidence_score": 0.92}]}'
                        }
                    }
                ],
            }
        }

        with patch("knowledge.scout.chat", return_value=fake_response):
            concepts = tag_content("recursive functions call themselves")

        self.assertEqual(len(concepts), 1)
        self.assertEqual(concepts[0].concept_tag, "Recursion")
        self.assertGreater(concepts[0].confidence_score, 0.9)

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

    def test_sage_strips_explanation_preamble_to_extract_socratic_question(self):
        """Verify that Sage can extract a real Socratic question from explanation preambles."""
        explanation_response = (
            "Atoms bond because they want to become more stable. "
            "They do this by either sharing or transferring electrons. "
            "Can you tell me what happens when electrons are transferred?"
        )
        
        result = _enforce_socratic_question(explanation_response)
        
        # Should extract the real Socratic question, not a generic fallback
        self.assertIn("transferred", result.lower())
        self.assertTrue(result.endswith("?"))
        self.assertGreater(len(result), 8)

    def test_sage_avoids_non_socratic_restatement_questions(self):
        """Verify that generic 'explain that' questions are avoided in favor of real Socratic ones."""
        response_with_restatement = (
            "Chemical bonding involves atoms sharing electrons to form stable molecules. "
            "Can you explain that in your own words, step by step?"
        )
        
        result = _enforce_socratic_question(response_with_restatement)
        
        # Should not return the generic restatement request
        self.assertNotIn("explain that", result.lower())
        # Should fall back to a proper Socratic question if no better option exists
        self.assertTrue(result.endswith("?"))

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

    def test_lens_parses_fenced_json_payload(self):
        fake_response = {
            "message": {
                "content": '```json\n{"x": 1, "y": 2, "width": 3, "height": 4, "explanation": "handwritten work", "handwritten": "true", "has_issue": "false", "confidence": 0.88}\n```',
                "audio": None,
            }
        }

        image_bytes = b"fake-image-bytes"
        with patch("knowledge.lens.Image.open") as mock_open, patch("knowledge.lens.chat", return_value=fake_response):
            mock_image = mock_open.return_value
            mock_image.width = 640
            mock_image.height = 480
            result = verify_image(image_bytes, "photosynthesis")

        self.assertTrue(result.handwritten)
        self.assertFalse(result.has_issue)
        self.assertEqual(result.width, 3)
        self.assertGreater(result.confidence, 0.8)


if __name__ == "__main__":
    unittest.main()

import unittest

from knowledge.sync import aggregator


class SyncPayloadTests(unittest.TestCase):
    def test_payload_is_minimal_and_privacy_preserving(self):
        original = aggregator.db.list_sync_concepts
        aggregator.db.list_sync_concepts = lambda: [
            {
                "concept": "Dynamic Programming",
                "status": "on_loan",
                "clearing_method": "sage_only",
                "lens_signature": "abc123",
                "integrity_suspect": 0,
                "source_text": "THIS MUST NEVER LEAK",
            }
        ]
        try:
            payload = aggregator.build_weekly_payload()
        finally:
            aggregator.db.list_sync_concepts = original

        self.assertIn("course_id", payload)
        self.assertIn("week", payload)
        self.assertIn("payload_hash", payload)
        self.assertEqual(len(payload["concepts"]), 1)

        concept = payload["concepts"][0]
        self.assertEqual(concept["concept"], "Dynamic Programming")
        self.assertNotIn("source_text", concept)
        self.assertNotIn("chat_history", concept)
        self.assertNotIn("typing_dynamics", concept)


if __name__ == "__main__":
    unittest.main()

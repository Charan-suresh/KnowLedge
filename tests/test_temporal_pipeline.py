import importlib
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient


class TemporalPipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)

        import knowledge.config as config
        self.config = config
        self.original_db_path = config.DB_PATH
        config.DB_PATH = str(Path(self.tmpdir.name) / "pipeline_test.db")

        import knowledge.db as db
        self.db = importlib.reload(db)
        self.db.init_db()
        self.db.run_migrations()

        import knowledge.main as main
        self.main = importlib.reload(main)

        from knowledge.sage import ClearingResult

        def fake_trigger_clearing(concept, chat_history, session_id=None, student_id=None, db_session_id=None):
            return ClearingResult(cleared=False, response="Thanks, keep going.")

        self.main.orchestrator.trigger_clearing = fake_trigger_clearing
        self.client = TestClient(self.main.app)

    def tearDown(self):
        self.config.DB_PATH = self.original_db_path

    def test_temporal_fingerprint_pipeline_end_to_end(self):
        payload = {
            "concept": "linked list",
            "session_id": "sage-test-123",
            "student_id": "student-temporal",
            "chat_history": [{"role": "user", "content": "It starts at head then traverses node by node."}],
            "temporal_fingerprint": {
                "time_to_first_keystroke": 3500,
                "is_paste_detected": False,
                "typing_cadence": [120, 180, 240, 90, 260],
                "edit_ratio": 0.8,
                "response_duration_ms": 14000,
                "response_length": 90,
                "question_complexity": "complex",
            },
        }

        response = self.client.post("/api/sage/turn", json=payload)
        self.assertEqual(response.status_code, 200)

        session_id = self.db.get_or_create_learning_session("student-temporal", "linked list")
        row = self.db.get_concept_score(session_id, "linked list")

        self.assertIsNotNone(row)
        self.assertGreaterEqual(float(row["temporal_score"]), 0.0)
        self.assertLessEqual(float(row["temporal_score"]), 1.0)


if __name__ == "__main__":
    unittest.main()

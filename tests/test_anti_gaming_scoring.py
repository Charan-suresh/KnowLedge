import tempfile
import unittest
from pathlib import Path

from knowledge import config, db
from knowledge.anti_gaming import score_temporal_fingerprint, compute_true_comprehension


class AntiGamingScoringTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.original_db_path = config.DB_PATH
        config.DB_PATH = str(Path(self.tmpdir.name) / "knowledge_test.db")
        db.init_db()
        db.run_migrations()

    def tearDown(self):
        config.DB_PATH = self.original_db_path

    def test_temporal_score_caps_for_long_paste(self):
        fp = {
            "time_to_first_keystroke": 250,
            "is_paste_detected": True,
            "typing_cadence": [10, 10, 10],
            "edit_ratio": 1.0,
            "response_duration_ms": 900,
            "response_length": 140,
            "question_complexity": "complex",
        }
        score = score_temporal_fingerprint(fp)
        self.assertLessEqual(score, 0.1)

    def test_temporal_score_high_for_organic_typing(self):
        fp = {
            "time_to_first_keystroke": 4200,
            "is_paste_detected": False,
            "typing_cadence": [120, 215, 180, 260, 143, 340],
            "edit_ratio": 0.76,
            "response_duration_ms": 18000,
            "response_length": 132,
            "question_complexity": "complex",
        }
        score = score_temporal_fingerprint(fp)
        self.assertGreaterEqual(score, 0.7)

    def test_update_comprehension_score_uses_required_weights(self):
        session_id = db.create_learning_session("student-1", "linked lists")
        out = db.update_comprehension_score(
            session_id=session_id,
            concept="linked lists",
            new_signal={
                "direct_answer_score": 0.8,
                "temporal_score": 0.6,
                "probe_depth_score": 0.5,
                "trap_score": 1.0,
            },
        )
        expected = compute_true_comprehension(
            direct_answer_score=0.8,
            temporal_score=0.6,
            probe_depth_score=0.5,
            trap_score=1.0,
        )
        self.assertAlmostEqual(out["true_comprehension"], expected, places=4)

    def test_status_auto_live_session_required_under_threshold(self):
        session_id = db.create_learning_session("student-2", "graphs")
        out = db.update_comprehension_score(
            session_id=session_id,
            concept="graphs",
            new_signal={
                "direct_answer_score": 0.2,
                "temporal_score": 0.1,
                "probe_depth_score": 0.3,
                "trap_score": 0.0,
            },
        )
        self.assertLess(out["true_comprehension"], 0.4)
        self.assertEqual(out["status"], "live_session_required")

    def test_get_student_debt_report_groups_low_comprehension(self):
        session_id = db.create_learning_session("student-3", "trees")
        db.update_comprehension_score(
            session_id=session_id,
            concept="trees",
            new_signal={
                "direct_answer_score": 0.2,
                "temporal_score": 0.2,
                "probe_depth_score": 0.2,
                "trap_score": 0.0,
            },
        )

        session_id_2 = db.create_learning_session("student-3", "hash tables")
        db.update_comprehension_score(
            session_id=session_id_2,
            concept="hash tables",
            new_signal={
                "direct_answer_score": 0.5,
                "temporal_score": 0.5,
                "probe_depth_score": 0.5,
                "trap_score": 0.5,
            },
        )

        report = db.get_student_debt_report("student-3")
        self.assertIn("live_session_required", report)
        self.assertGreaterEqual(len(report["live_session_required"]), 1)


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path

from knowledge import config
from knowledge.integrity.anti_spoof import analyze_integrity
from knowledge.integrity.session_fingerprint import sign_fingerprint, verify_session_hash


class IntegrityCoreTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.original_key_path = config.DEVICE_KEY_PATH
        config.DEVICE_KEY_PATH = str(Path(self.tmpdir.name) / "device.key")

    def tearDown(self):
        config.DEVICE_KEY_PATH = self.original_key_path

    def test_signature_roundtrip(self):
        fp = {
            "session_id": "s1",
            "concept": "Recursion",
            "total_duration_seconds": 88,
            "turn_count": 4,
            "response_times": [2.3, 1.9, 2.4],
            "response_lengths": [22, 31, 19],
            "timeout_count": 0,
            "median_response_time": 2.3,
            "response_time_variance": 0.06,
            "backspace_events": 12,
            "paste_detected": False,
            "language_detected": "en",
        }
        session_hash = sign_fingerprint(fp)
        self.assertTrue(verify_session_hash(fp, session_hash))

    def test_anti_spoof_flags_paste_and_timeout_pattern(self):
        fp = {
            "response_time_variance": 40.0,
            "median_response_time": 0.4,
            "timeout_count": 4,
            "paste_detected": True,
            "turn_count": 5,
        }
        result = analyze_integrity(fp)
        self.assertTrue(result["integrity_suspect"])
        self.assertGreaterEqual(result["spoof_attempts"], 2)


if __name__ == "__main__":
    unittest.main()

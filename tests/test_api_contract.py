import unittest
from fastapi.testclient import TestClient

from knowledge.main import app


class ApiContractTests(unittest.TestCase):
    def test_sync_and_integrity_endpoints(self):
        with TestClient(app) as client:
            r1 = client.get("/api/sync/status")
            self.assertEqual(r1.status_code, 200)
            self.assertIn("pending_count", r1.json())

            r2 = client.get("/api/integrity/report")
            self.assertEqual(r2.status_code, 200)
            body = r2.json()
            self.assertIn("sessions_with_signatures", body)
            self.assertIn("spoof_attempts", body)

            r3 = client.post("/api/sync/share-weekly")
            self.assertEqual(r3.status_code, 200)
            self.assertIn("status", r3.json())


if __name__ == "__main__":
    unittest.main()

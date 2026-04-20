import unittest
from unittest.mock import patch

import httpx

from knowledge.agents import hf_client


class HfClientTests(unittest.IsolatedAsyncioTestCase):
    def test_normalize_space_base_url_from_slug(self):
        self.assertEqual(
            hf_client._normalize_space_base_url("charan-ml/knowledge-inference"),
            "https://charan-ml-knowledge-inference.hf.space",
        )

    async def test_check_health_uses_fastapi_health_endpoint(self):
        called_urls = []

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {"status": "ok"}

        class FakeAsyncClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def request(self, method, url, json=None):
                called_urls.append(url)
                return FakeResponse()

        with patch.object(hf_client, "HF_SPACE_URL", "charan-ml/knowledge-inference"):
            with patch("knowledge.agents.hf_client.httpx.AsyncClient", FakeAsyncClient):
                ok = await hf_client.check_health()

        self.assertTrue(ok)
        self.assertEqual(
            called_urls,
            ["https://charan-ml-knowledge-inference.hf.space/api/health"],
        )

    async def test_get_health_status_reports_error_details(self):
        class FakeAsyncClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def request(self, method, url, json=None):
                raise httpx.ConnectError("boom")

        with patch.object(hf_client, "HF_SPACE_URL", "charan-ml/knowledge-inference"):
            with patch("knowledge.agents.hf_client.httpx.AsyncClient", FakeAsyncClient):
                status = await hf_client.get_health_status()

        self.assertFalse(status["reachable"])
        self.assertIn("ConnectError", status["error"])
        self.assertEqual(
            status["base_url"],
            "https://charan-ml-knowledge-inference.hf.space",
        )

    async def test_request_retries_without_tls_verification_on_cert_error(self):
        calls = []

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {"status": "ok"}

        class FakeAsyncClient:
            def __init__(self, *args, **kwargs):
                self.verify = kwargs.get("verify", True)

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def request(self, method, url, json=None):
                calls.append((self.verify, method, url))
                if self.verify is True:
                    raise httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed")
                return FakeResponse()

        with patch.object(hf_client, "HF_SPACE_URL", "charan-ml/knowledge-inference"):
            with patch("knowledge.agents.hf_client.httpx.AsyncClient", FakeAsyncClient):
                response = await hf_client._request("GET", "/api/health")

        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(
            calls,
            [
                (True, "GET", "https://charan-ml-knowledge-inference.hf.space/api/health"),
                (False, "GET", "https://charan-ml-knowledge-inference.hf.space/api/health"),
            ],
        )


if __name__ == "__main__":
    unittest.main()

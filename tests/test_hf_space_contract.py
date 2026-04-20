import unittest
import importlib
import sys
import types
from fastapi.testclient import TestClient


class HfSpaceContractTests(unittest.TestCase):
    def test_generate_returns_structured_error_payload(self):
        fake_inference = types.ModuleType("inference")
        fake_inference.generate_with_image = lambda *args, **kwargs: "ok"
        fake_inference.health_check = lambda: {"status": "ok"}

        def boom(*args, **kwargs):
            raise RuntimeError("model load failed")

        fake_inference.generate_text = boom

        original_hf_space_app = sys.modules.pop("hf_space.app", None)
        original_inference = sys.modules.get("inference")
        sys.modules["inference"] = fake_inference
        try:
            module = importlib.import_module("hf_space.app")
            with TestClient(module.app) as client:
                response = client.post(
                    "/api/generate",
                    json={"model": "e2b", "prompt": "hello", "max_tokens": 8},
                )
        finally:
            sys.modules.pop("hf_space.app", None)
            if original_hf_space_app is not None:
                sys.modules["hf_space.app"] = original_hf_space_app
            if original_inference is not None:
                sys.modules["inference"] = original_inference
            else:
                sys.modules.pop("inference", None)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"error": "model load failed"})


if __name__ == "__main__":
    unittest.main()

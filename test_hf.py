"""Manual Hugging Face Space smoke script.

This file is intentionally not a pytest test module. Run it directly:
    ./.venv/bin/python test_hf.py
"""

__test__ = False

import json
import urllib.request


def main() -> int:
    try:
        req = urllib.request.Request(
            "https://charan-ml-knowledge-inference.hf.space/api/generate",
            data=json.dumps({"model": "e2b", "prompt": "Hello", "max_tokens": 50}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as response:
            body = response.read().decode("utf-8")
        print("Raw Response:", body)
        return 0
    except Exception as exc:
        print("HF Space Exception:", str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

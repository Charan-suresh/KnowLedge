import os
import sys
import traceback

from fastapi.testclient import TestClient

try:
    from knowledge.main import app
except Exception:
    traceback.print_exc()
    sys.exit(1)


CORE_ENDPOINTS = [
    ("GET", "/health", None),
    ("GET", "/api/status", None),
    ("GET", "/ledger", None),
]

RUN_LLM_SMOKE = os.getenv("RUN_LLM_SMOKE", "0") == "1"
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")


def print_response(method: str, url: str, response) -> None:
    content_type = response.headers.get("content-type", "")
    print(f"{method} {url} - Status: {response.status_code}")
    if "application/json" in content_type:
        print(f"Response: {response.json()}")
    else:
        print(f"Response: {response.text[:160]}")


with TestClient(app) as client:
    for method, url, json_data in CORE_ENDPOINTS:
        try:
            response = client.get(url) if method == "GET" else client.post(url, json=json_data)
            print_response(method, url, response)
        except Exception as exc:
            print(f"Error calling {method} {url}: {exc}")
            traceback.print_exc()
            sys.exit(1)

    if RUN_LLM_SMOKE:
        payload = {
            "content": "Photosynthesis uses sunlight, water, and carbon dioxide to produce glucose and oxygen.",
            "student_id": "smoke",
            "session_id": "smoke-session",
            "ollama_url": OLLAMA_URL,
        }
        try:
            response = client.post("/api/scout", json=payload)
            print_response("POST", "/api/scout", response)
        except Exception as exc:
            print(f"Error calling POST /api/scout: {exc}")
            traceback.print_exc()
            sys.exit(1)

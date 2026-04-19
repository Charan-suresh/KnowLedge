import sys
import traceback
from fastapi.testclient import TestClient

try:
    from knowledge.main import app
except Exception:
    traceback.print_exc()
    sys.exit(1)

endpoints = [
    ("GET", "/api/sync/status", None),
    ("GET", "/api/integrity/report", None),
    ("POST", "/api/sync/share-weekly", None),
]

with TestClient(app) as client:
    for method, url, json_data in endpoints:
        try:
            if method == "GET":
                response = client.get(url)
            elif method == "POST":
                response = client.post(url, json=json_data)

            print(f"{method} {url} - Status: {response.status_code}")
            print(f"Response: {response.json() if response.headers.get('content-type') == 'application/json' else response.text[:100]}")
        except Exception as e:
            print(f"Error calling {method} {url}: {e}")
            traceback.print_exc()
            sys.exit(1)

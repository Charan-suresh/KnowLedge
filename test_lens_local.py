import asyncio
from fastapi import Request
from knowledge.main import app, lens
from starlette.testclient import TestClient

client = TestClient(app)

with open("test.jpg", "wb") as f:
    f.write(b"fake image data")

with open("test.jpg", "rb") as f:
    response = client.post("/api/lens", files={"file": f}, data={"document_type": "auto", "student_id": "test"})
    print(response.status_code)
    print(response.text)

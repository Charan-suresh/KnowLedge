import json
from typing import Any, AsyncGenerator, Dict, List

import httpx

from ..config import OLLAMA_BASE_URL, OLLAMA_AUTH_TOKEN


def _headers() -> Dict[str, str]:
    """Return auth headers if token is configured."""
    headers = {"Content-Type": "application/json"}
    if OLLAMA_AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {OLLAMA_AUTH_TOKEN}"
    return headers


async def generate(model: str, prompt: str, stream: bool = False):
    """Call Ollama /api/generate in non-streaming or streaming mode."""
    url = f"{OLLAMA_BASE_URL}/api/generate"
    payload = {"model": model, "prompt": prompt, "stream": stream}

    if not stream:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, json=payload, headers=_headers())
            response.raise_for_status()
            return response.json()
    return _stream_generate(url, payload)


async def _stream_generate(url: str, payload: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream("POST", url, json=payload, headers=_headers()) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line:
                    yield json.loads(line)


async def generate_with_image(model: str, prompt: str, image_base64: str) -> Dict[str, Any]:
    """Vision helper passing a single base64 image to /api/generate."""
    url = f"{OLLAMA_BASE_URL}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "images": [image_base64],
        "stream": False,
    }
    async with httpx.AsyncClient(timeout=180.0) as client:
        response = await client.post(url, json=payload, headers=_headers())
        response.raise_for_status()
        return response.json()


async def check_health() -> bool:
    """Return True if Ollama tags endpoint is reachable."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/tags", headers=_headers())
            return response.status_code == 200
    except Exception:
        return False


async def list_models() -> List[str]:
    """Return available model tags from Ollama."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"{OLLAMA_BASE_URL}/api/tags", headers=_headers())
        response.raise_for_status()
        return [m.get("name", "") for m in response.json().get("models", []) if m.get("name")]


def chat(model: str, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]] | None = None, format: str | None = None, num_predict: int = 512) -> Dict[str, Any]:
    """Synchronous /api/chat helper for non-async call sites."""
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": False,
        "options": {"num_predict": num_predict, "temperature": 0.7},
    }
    if tools:
        payload["tools"] = tools
    if format:
        payload["format"] = format

    with httpx.Client(timeout=120.0) as client:
        response = client.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, headers=_headers())
        response.raise_for_status()
        return response.json()


async def chat_async(model: str, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]] | None = None, format: str | None = None) -> Dict[str, Any]:
    """Async /api/chat helper for non-streaming responses."""
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": False,
        "options": {"num_predict": 512, "temperature": 0.7},
    }
    if tools:
        payload["tools"] = tools
    if format:
        payload["format"] = format

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, headers=_headers())
        response.raise_for_status()
        return response.json()


async def stream_chat(model: str, messages: List[Dict[str, Any]]) -> AsyncGenerator[Dict[str, Any], None]:
    """Async streaming /api/chat helper yielding JSON chunks."""
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "think": False,
        "options": {"num_predict": 512, "temperature": 0.7},
    }
    async with httpx.AsyncClient(timeout=180.0) as client:
        async with client.stream("POST", f"{OLLAMA_BASE_URL}/api/chat", json=payload, headers=_headers()) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line:
                    yield json.loads(line)

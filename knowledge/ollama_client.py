import json
import re
from typing import Optional

import httpx

OLLAMA_BASE = "http://localhost:11434"
MODEL_PREFERENCE = [
    "gemma4:e4b-q4_K_M",
    "gemma4:e4b",
    "gemma3:4b",
    "gemma3:1b",
]

_resolved_model: Optional[str] = None


def resolve_model(base_url: str = OLLAMA_BASE) -> Optional[str]:
    global _resolved_model
    try:
        response = httpx.get(f"{base_url}/api/tags", timeout=5.0)
        available = [model["name"] for model in response.json().get("models", [])]
        for preferred in MODEL_PREFERENCE:
            for candidate in available:
                if preferred.split(":")[0] in candidate:
                    _resolved_model = candidate
                    return candidate
        if available:
            _resolved_model = available[0]
            return available[0]
    except Exception:
        pass
    return None


def get_model(base_url: str = OLLAMA_BASE) -> str:
    return _resolved_model or resolve_model(base_url) or "gemma4:e4b"


def chat(
    system: str,
    user: str,
    base_url: str = OLLAMA_BASE,
    images: list[str] | None = None,
    temperature: float = 0.7,
) -> str:
    model = get_model(base_url)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "options": {"temperature": temperature},
    }
    if images:
        payload["messages"][1]["images"] = images

    try:
        response = httpx.post(
            f"{base_url}/api/chat",
            json=payload,
            timeout=120.0,
        )
        response.raise_for_status()
        return response.json()["message"]["content"].strip()
    except httpx.TimeoutException as exc:
        raise RuntimeError("Ollama timed out. Is it running?") from exc
    except Exception as exc:
        raise RuntimeError(f"Ollama error: {exc}") from exc


def extract_json(text: str) -> dict | list:
    text = re.sub(r"```(?:json)?", "", text).strip()
    text = text.replace("```", "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for pattern in [r"\{[^{}]*\}", r"\[[^\[\]]*\]"]:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                continue
    raise ValueError(f"No valid JSON found in: {text[:200]}")


def is_ready(base_url: str = OLLAMA_BASE) -> dict:
    try:
        response = httpx.get(f"{base_url}/api/tags", timeout=3.0)
        models = [model["name"] for model in response.json().get("models", [])]
        model = resolve_model(base_url)
        return {
            "ready": model is not None,
            "model": model or "none",
            "all_models": models,
            "ollama_running": True,
        }
    except Exception:
        return {
            "ready": False,
            "model": None,
            "all_models": [],
            "ollama_running": False,
        }

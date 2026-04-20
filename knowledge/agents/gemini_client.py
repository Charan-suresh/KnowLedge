import asyncio
from typing import AsyncGenerator

import httpx

from ..config import GEMINI_API_KEY

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

MODEL_MAP = {
    "gemma4:e2b": "gemma-4-e2b-it",
    "gemma4:e4b": "gemma-4-e4b-it",
    "e2b": "gemma-4-e2b-it",
    "e4b": "gemma-4-e4b-it",
}


async def generate(model: str, prompt: str, max_tokens: int = 512) -> dict:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY environment variable is not set")

    gemini_model = MODEL_MAP.get(model, "gemma-4-e4b-it")
    url = f"{GEMINI_BASE_URL}/models/{gemini_model}:generateContent"

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens},
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(url, json=payload, params={"key": GEMINI_API_KEY})
        response.raise_for_status()
        data = response.json()

    text = data["candidates"][0]["content"]["parts"][0].get("text", "")
    return {"response": text}


async def generate_with_image(
    model: str, prompt: str, image_base64: str, max_tokens: int = 512
) -> dict:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY environment variable is not set")

    gemini_model = MODEL_MAP.get(model, "gemma-4-e4b-it")
    url = f"{GEMINI_BASE_URL}/models/{gemini_model}:generateContent"

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": image_base64,
                        }
                    },
                    {"text": prompt},
                ]
            }
        ],
        "generationConfig": {"maxOutputTokens": max_tokens},
    }

    async with httpx.AsyncClient(timeout=180.0) as client:
        response = await client.post(url, json=payload, params={"key": GEMINI_API_KEY})
        response.raise_for_status()
        data = response.json()

    text = data["candidates"][0]["content"]["parts"][0].get("text", "")
    return {"response": text}


async def check_health() -> bool:
    if not GEMINI_API_KEY:
        return False
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{GEMINI_BASE_URL}/models",
                params={"key": GEMINI_API_KEY},
            )
            return response.status_code == 200
    except Exception:
        return False


async def generate_stream(
    model: str, prompt: str, max_tokens: int = 512
) -> AsyncGenerator[dict, None]:
    result = await generate(model, prompt, max_tokens)
    words = result["response"].split(" ") if result.get("response") else []
    for i, word in enumerate(words):
        yield {
            "response": word + (" " if i < len(words) - 1 else ""),
            "done": i == len(words) - 1,
        }
        await asyncio.sleep(0.03)

import asyncio
import json
from typing import AsyncGenerator

from gradio_client import Client

from ..config import HF_SPACE_URL

_client: Client | None = None


def _get_client() -> Client:
    """Lazily initialize and cache the Gradio client."""
    global _client
    if _client is None:
        if not HF_SPACE_URL:
            raise ValueError("HF_SPACE_URL environment variable is not set")
        _client = Client(HF_SPACE_URL)
    return _client


async def generate(model: str, prompt: str, max_tokens: int = 512) -> dict:
    payload = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "max_tokens": max_tokens,
        }
    )

    loop = asyncio.get_running_loop()
    raw = await loop.run_in_executor(
        None,
        lambda: _get_client().predict(payload, api_name="/generate"),
    )

    result = json.loads(raw)
    if result.get("error"):
        raise RuntimeError(f"HF Space error: {result['error']}")
    return {"response": result.get("response", "")}


async def generate_with_image(
    model: str, prompt: str, image_base64: str, max_tokens: int = 512
) -> dict:
    payload = json.dumps(
        {
            "prompt": prompt,
            "image_base64": image_base64,
            "max_tokens": max_tokens,
        }
    )

    loop = asyncio.get_running_loop()
    raw = await loop.run_in_executor(
        None,
        lambda: _get_client().predict(payload, api_name="/generate_vision"),
    )

    result = json.loads(raw)
    if result.get("error"):
        raise RuntimeError(f"HF Space vision error: {result['error']}")
    return {"response": result.get("response", "")}


async def check_health() -> bool:
    try:
        loop = asyncio.get_running_loop()
        raw = await loop.run_in_executor(
            None,
            lambda: _get_client().predict(api_name="/health"),
        )
        result = json.loads(raw)
        return result.get("status") == "ok"
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

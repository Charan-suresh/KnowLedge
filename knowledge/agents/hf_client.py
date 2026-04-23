import asyncio
from typing import AsyncGenerator

import httpx

from ..config import HF_SPACE_URL

_last_health_error = ""


def _normalize_space_base_url(space_ref: str) -> str:
    value = (space_ref or "").strip().rstrip("/")
    if not value:
        raise ValueError("HF_SPACE_URL environment variable is not set")

    if value.startswith(("http://", "https://")):
        if "huggingface.co/spaces/" in value:
            slug = value.split("huggingface.co/spaces/", 1)[1].strip("/")
            owner, space = slug.split("/", 1)
            return f"https://{owner}-{space}.hf.space"
        return value

    if "/" in value:
        owner, space = value.split("/", 1)
        return f"https://{owner}-{space}.hf.space"

    return value


def _base_url() -> str:
    return _normalize_space_base_url(HF_SPACE_URL)


async def _request(method: str, path: str, json: dict | None = None, timeout: float = 30.0) -> httpx.Response:
    url = f"{_base_url()}{path}"
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.request(method, url, json=json)
            _raise_for_status_with_context(response)
            return response
    except httpx.ConnectError as exc:
        if "certificate verify failed" not in str(exc).lower():
            raise

    # Retry without TLS verification when the HF Space certificate causes issues.
    async with httpx.AsyncClient(timeout=timeout, verify=False, follow_redirects=True) as client:
        response = await client.request(method, url, json=json)
        _raise_for_status_with_context(response)
        return response


def _raise_for_status_with_context(response: httpx.Response) -> None:
    """
    Raise a descriptive error for non-2xx responses.

    HF Spaces that are sleeping return 503 with an HTML wake-up page.
    We detect this and raise a more actionable error than the raw HTTP error.
    """
    if response.is_success:
        return

    status = response.status_code
    content_type = response.headers.get("content-type", "")

    # HF Space is waking up (sleeping free-tier space)
    if status in (503, 502) or (status == 200 and "text/html" in content_type):
        raise RuntimeError(
            f"HF Space is unavailable (HTTP {status}). "
            "The Space may be waking from sleep — please retry in 20–30 seconds."
        )

    response.raise_for_status()


def _describe_exception(exc: Exception) -> str:
    name = exc.__class__.__name__
    message = str(exc).strip()
    return f"{name}: {message}" if message else name


async def generate(model: str, prompt: str, max_tokens: int = 512) -> dict:
    payload = {
        "model": model,
        "prompt": prompt,
        "max_tokens": max_tokens,
    }

    response = await _request("POST", "/api/generate", json=payload, timeout=240.0)

    try:
        result = response.json()
    except Exception:
        raise RuntimeError(
            f"HF Space returned non-JSON response (status {response.status_code}). "
            "The Space may be waking from sleep — please retry in 20–30 seconds."
        )

    if result.get("error"):
        raise RuntimeError(f"HF Space inference error: {result['error']}")
    return {"response": result.get("response", "")}


async def generate_with_image(
    model: str, prompt: str, image_base64: str, max_tokens: int = 512
) -> dict:
    payload = {
        "prompt": prompt,
        "image_base64": image_base64,
        "max_tokens": max_tokens,
    }

    response = await _request("POST", "/api/generate_vision", json=payload, timeout=240.0)

    try:
        result = response.json()
    except Exception:
        raise RuntimeError(
            f"HF Space returned non-JSON response for vision (status {response.status_code}). "
            "The Space may be waking from sleep — please retry in 20–30 seconds."
        )

    if result.get("error"):
        raise RuntimeError(f"HF Space vision error: {result['error']}")
    return {"response": result.get("response", "")}


async def check_health() -> bool:
    return (await get_health_status()).get("reachable", False)


async def get_health_status() -> dict:
    global _last_health_error
    try:
        response = await _request("GET", "/api/health", timeout=15.0)
        result = response.json()
        reachable = result.get("status") == "ok"
        _last_health_error = "" if reachable else f"Unexpected health payload: {result!r}"
        return {
            "reachable": reachable,
            "base_url": _base_url(),
            "error": _last_health_error or None,
            "response": result,
        }
    except Exception as exc:
        _last_health_error = _describe_exception(exc)
        return {
            "reachable": False,
            "base_url": _base_url(),
            "error": _last_health_error,
            "response": None,
        }


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

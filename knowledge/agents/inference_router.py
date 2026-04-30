from __future__ import annotations

import re
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

from .. import config
from . import ollama_client


def _backend() -> str:
    return (config.INFERENCE_BACKEND or "hf_space").strip().lower()


def _is_hf_backend() -> bool:
    return _backend() in {"hf_space", "huggingface"}


def _hf_base_url(base_url: Optional[str] = None) -> str:
    candidate = (base_url or config.HF_SPACE_URL or config.OLLAMA_BASE_URL or "").strip().rstrip("/")
    if candidate.startswith("https://huggingface.co/spaces/"):
        parts = candidate.split("/")
        if len(parts) >= 6:
            return f"https://{parts[4]}-{parts[5]}.hf.space"
    return candidate


def _messages_to_prompt(messages: List[Dict[str, Any]]) -> str:
    parts: List[str] = []
    for message in messages:
        role = (message.get("role") or "user").strip().lower()
        content = (message.get("content") or "").strip()
        if not content:
            continue
        label = "System" if role == "system" else "Assistant" if role == "assistant" else "User"
        parts.append(f"[{label}]\n{content}")
    return "\n\n".join(parts).strip()


def _extract_image(messages: List[Dict[str, Any]]) -> Optional[str]:
    for message in reversed(messages):
        images = message.get("images") or []
        if images:
            return str(images[0]).strip()
    return None


def _tool_call_response(text: str, tools: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
    content = (text or "").strip()
    message: Dict[str, Any] = {"role": "assistant", "content": content}
    if not tools:
        return {"message": message, "response": content}

    tool_names = {tool.get("function", {}).get("name") for tool in tools if isinstance(tool, dict)}
    tool_calls: List[Dict[str, Any]] = []

    if "verify_comprehension" in tool_names and re.search(r"\bCLEARED\b", content, re.IGNORECASE):
        tool_calls.append(
            {
                "type": "function",
                "function": {
                    "name": "verify_comprehension",
                    "arguments": "{\"reasoning\":\"HF backend signalled mastery\"}",
                },
            }
        )

    if tool_calls:
        message["tool_calls"] = tool_calls

    return {"message": message, "response": content}


def chat(
    model: str,
    messages: List[Dict[str, Any]],
    tools: List[Dict[str, Any]] | None = None,
    format: str | None = None,
    num_predict: int = 512,
) -> Dict[str, Any]:
    if not _is_hf_backend():
        return ollama_client.chat(model=model, messages=messages, tools=tools, format=format, num_predict=num_predict)

    base_url = _hf_base_url()
    prompt = _messages_to_prompt(messages)
    image = _extract_image(messages)
    payload: Dict[str, Any]
    endpoint = "/api/generate"

    if image:
        payload = {
            "prompt": prompt,
            "image_base64": image,
            "model": model,
            "max_tokens": num_predict,
        }
        endpoint = "/api/generate_vision"
    else:
        payload = {
            "prompt": prompt,
            "model": model,
            "max_tokens": num_predict,
        }

    if format == "json":
        payload["format"] = "json"

    if tools:
        tool_names = ", ".join(sorted(tool.get("function", {}).get("name", "") for tool in tools if isinstance(tool, dict)))
        if tool_names:
            payload["prompt"] = f"{prompt}\n\nAvailable tools: {tool_names}. Follow the instructions exactly."

    try:
        response = httpx.post(f"{base_url}{endpoint}", json=payload, timeout=120.0)
        response.raise_for_status()
        body = response.json()
        text = (body.get("response") or body.get("text") or body.get("output") or "").strip()
        return _tool_call_response(text, tools)
    except Exception as exc:
        raise RuntimeError(f"HF Space error: {exc}") from exc


async def chat_async(
    model: str,
    messages: List[Dict[str, Any]],
    tools: List[Dict[str, Any]] | None = None,
    format: str | None = None,
    num_predict: int = 512,
) -> Dict[str, Any]:
    return chat(model=model, messages=messages, tools=tools, format=format, num_predict=num_predict)


async def stream_chat(model: str, messages: List[Dict[str, Any]]) -> AsyncGenerator[Dict[str, Any], None]:
    if not _is_hf_backend():
        async for chunk in ollama_client.stream_chat(model=model, messages=messages):
            yield chunk
        return

    yield chat(model=model, messages=messages)


def is_ready(base_url: str | None = None) -> Dict[str, Any]:
    if not _is_hf_backend():
        return ollama_client.is_ready(base_url or config.OLLAMA_BASE_URL)

    target = _hf_base_url(base_url)
    if not target:
        return {
            "ready": False,
            "model": None,
            "all_models": [],
            "ollama_running": False,
            "ollama_url": target,
            "required_model": config.REQUIRED_MODEL,
            "required_model_loaded": False,
        }

    try:
        response = httpx.get(f"{target}/api/health", timeout=5.0)
        response.raise_for_status()
        health = response.json()
        model_name = health.get("model_file") or health.get("model_repo") or "hf-space-model"
        model_loaded = bool(health.get("model_loaded", False))
        return {
            "ready": model_loaded,
            "model": model_name,
            "all_models": [model_name] if model_loaded else [],
            "ollama_running": True,
            "ollama_url": target,
            "required_model": config.REQUIRED_MODEL,
            "required_model_loaded": model_loaded,
        }
    except Exception:
        return {
            "ready": False,
            "model": None,
            "all_models": [],
            "ollama_running": False,
            "ollama_url": target,
            "required_model": config.REQUIRED_MODEL,
            "required_model_loaded": False,
        }
"""
Inference router that selects backend using INFERENCE_BACKEND.

Backends:
- hf_space   : Hugging Face ZeroGPU Space (primary)
- gemini_api : Gemini API (fallback)
- ollama     : Local Ollama (development default)

The hf_space/ directory in this repo is a standalone Space template only.
Deploy it to a separate Hugging Face Space repository, not this Render app.
"""

import asyncio
import json
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, AsyncGenerator, Dict, List


def _current_backend() -> str:
    return os.getenv("INFERENCE_BACKEND", "ollama").strip().lower() or "ollama"


def _get_client():
    backend = _current_backend()
    if backend == "hf_space":
        from . import hf_client as client
    elif backend == "gemini_api":
        from . import gemini_client as client
    else:
        from . import ollama_client as client
    return client


def _messages_to_prompt(messages: List[Dict[str, Any]]) -> str:
    chunks: List[str] = []
    for msg in messages:
        role = msg.get("role", "user").upper()
        content = msg.get("content", "")
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
            content = "\n".join(part for part in text_parts if part)
        chunks.append(f"[{role}]\n{content}")
    return "\n\n".join(chunks)


def _build_tooling_instructions(tools: List[Dict[str, Any]], format_name: str | None) -> str:
    instructions = []
    if tools:
        instructions.append(
            "You must output JSON with keys: 'content' and 'tool_calls'. "
            "tool_calls must be an array of objects in the form "
            "{'function': {'name': <tool_name>, 'arguments': <object>}}."
        )
        instructions.append(f"Available tools schema: {json.dumps(tools)}")
    if format_name == "json":
        instructions.append("Return strict JSON only. No markdown, no extra text.")
    return "\n".join(instructions)


def _extract_json_object(raw: str) -> Dict[str, Any] | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except Exception:
        pass

    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        data = json.loads(raw[start : end + 1])
        return data if isinstance(data, dict) else None
    except Exception:
        return None


async def generate(model: str, prompt: str, max_tokens: int = 512) -> dict:
    return await _get_client().generate(model, prompt, max_tokens)


async def generate_with_image(
    model: str, prompt: str, image_base64: str, max_tokens: int = 512
) -> dict:
    return await _get_client().generate_with_image(model, prompt, image_base64, max_tokens)


async def check_health() -> bool:
    return await _get_client().check_health()


async def generate_stream(
    model: str, prompt: str, max_tokens: int = 512
) -> AsyncGenerator[dict, None]:
    async for chunk in _get_client().generate_stream(model, prompt, max_tokens):
        yield chunk


async def stream_chat(model: str, messages: List[Dict[str, Any]]) -> AsyncGenerator[Dict[str, Any], None]:
    client = _get_client()
    if hasattr(client, "stream_chat") and _current_backend() == "ollama":
        async for chunk in client.stream_chat(model=model, messages=messages):
            yield chunk
        return

    prompt = _messages_to_prompt(messages)
    async for chunk in client.generate_stream(model=model, prompt=prompt, max_tokens=512):
        yield {
            "message": {"content": chunk.get("response", "")},
            "done": chunk.get("done", False),
        }


async def chat_async(
    model: str,
    messages: List[Dict[str, Any]],
    tools: List[Dict[str, Any]] | None = None,
    format: str | None = None,
) -> Dict[str, Any]:
    client = _get_client()
    if hasattr(client, "chat_async") and _current_backend() == "ollama":
        return await client.chat_async(model=model, messages=messages, tools=tools, format=format)

    prompt = _messages_to_prompt(messages)
    prompt_instructions = _build_tooling_instructions(tools or [], format)
    if prompt_instructions:
        prompt = f"{prompt}\n\n{prompt_instructions}"

    # If image payload exists in the final user message, route via vision call.
    image_b64 = ""
    for msg in reversed(messages):
        if isinstance(msg, dict) and msg.get("images"):
            images = msg.get("images") or []
            if images:
                image_b64 = images[0]
                break

    if image_b64:
        result = await client.generate_with_image(model, prompt, image_b64, 512)
    else:
        result = await client.generate(model, prompt, 512)

    response_text = result.get("response", "")

    parsed = _extract_json_object(response_text) if (tools or format == "json") else None
    content = response_text
    tool_calls: List[Dict[str, Any]] = []

    if parsed:
        content = parsed.get("content", content)
        if isinstance(parsed.get("tool_calls"), list):
            tool_calls = parsed["tool_calls"]
        elif tools:
            # Best-effort compatibility when model returns plain tool arguments.
            name = tools[0].get("function", {}).get("name", "tool_call")
            arguments = parsed
            tool_calls = [{"function": {"name": name, "arguments": arguments}}]

    return {
        "message": {
            "content": content,
            "tool_calls": tool_calls,
        }
    }


def _run_coroutine_sync(coro: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(lambda: asyncio.run(coro)).result()


def chat(
    model: str,
    messages: List[Dict[str, Any]],
    tools: List[Dict[str, Any]] | None = None,
    format: str | None = None,
) -> Dict[str, Any]:
    return _run_coroutine_sync(chat_async(model=model, messages=messages, tools=tools, format=format))

import json
import re
from typing import Optional
from urllib.parse import urlparse

import httpx

from . import config

OLLAMA_BASE = config.OLLAMA_BASE_URL
MODEL_PREFERENCE = [
    "gemma4:e4b",
    "gemma3:4b",
    "gemma3:1b",
]

_resolved_model: Optional[str] = None


def _required_model() -> str:
    return getattr(config, "REQUIRED_MODEL", "gemma4:e4b")


def _strict_required_model() -> bool:
    return bool(getattr(config, "STRICT_REQUIRED_MODEL", True))


def _normalize_model_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _matches_required_model(candidate: str, required: Optional[str] = None) -> bool:
    if not candidate:
        return False

    required = (required or _required_model()).strip().lower()
    candidate_norm = _normalize_model_name(candidate)

    # Strict handling for Gemma4:E4B aliases used by different backends.
    if required == "gemma4:e4b":
        return (
            ("gemma4" in candidate_norm and ("e4b" in candidate_norm or "4b" in candidate_norm))
            or candidate_norm in {"e4b", "4b"}
        )

    if ":" in required:
        family, variant = required.split(":", 1)
    else:
        family, variant = required, ""
    family_norm = _normalize_model_name(family)
    variant_norm = _normalize_model_name(variant)

    if family_norm and family_norm not in candidate_norm:
        return False
    if variant_norm and variant_norm not in candidate_norm and candidate_norm != variant_norm:
        return False
    return True


def _hf_model_hint() -> str:
    required = _required_model()
    if ":" in required:
        return required.split(":", 1)[1]
    return required


def _normalize_hf_space_url(base_url: str) -> str:
    """
    Accept either:
    - https://<owner>-<space>.hf.space
    - https://huggingface.co/spaces/<owner>/<space>
    and return the hf.space app URL.
    """
    parsed = urlparse(base_url)
    host = (parsed.netloc or "").lower()
    path = (parsed.path or "").strip("/")

    if host.endswith(".hf.space"):
        return f"{parsed.scheme or 'https'}://{parsed.netloc}".rstrip("/")

    if host == "huggingface.co" and path.startswith("spaces/"):
        parts = path.split("/")
        if len(parts) >= 3:
            owner, space = parts[1], parts[2]
            return f"https://{owner}-{space}.hf.space"

    return base_url.rstrip("/")


def _is_hf_space_base_url(base_url: str) -> bool:
    try:
        host = urlparse(base_url).netloc.lower()
    except Exception:
        return False
    return host.endswith(".hf.space") or host == "huggingface.co"


def _normalize_base_url(base_url: Optional[str] = None) -> str:
    candidate = (base_url or config.OLLAMA_BASE_URL or OLLAMA_BASE).rstrip("/")
    if _is_hf_space_base_url(candidate):
        return _normalize_hf_space_url(candidate)
    return candidate


def _headers() -> dict[str, str]:
    headers = {}
    if config.OLLAMA_AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {config.OLLAMA_AUTH_TOKEN}"
    return headers


def resolve_model(base_url: str = OLLAMA_BASE) -> Optional[str]:
    global _resolved_model
    base_url = _normalize_base_url(base_url)
    try:
        response = httpx.get(f"{base_url}/api/tags", timeout=5.0, headers=_headers())
        available = [model["name"] for model in response.json().get("models", [])]

        if _strict_required_model():
            for candidate in available:
                if _matches_required_model(candidate):
                    _resolved_model = candidate
                    return candidate
            return None

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
    base_url = _normalize_base_url(base_url)
    return _resolved_model or resolve_model(base_url) or "gemma4:e4b"


def chat(
    system: str,
    user: str,
    base_url: str = OLLAMA_BASE,
    images: list[str] | None = None,
    temperature: float = 0.7,
) -> str:
    base_url = _normalize_base_url(base_url)
    if base_url.endswith(".hf.space"):
        health_model_name = ""
        if _strict_required_model():
            try:
                health_response = httpx.get(f"{base_url}/api/health", timeout=5.0, headers=_headers())
                health_response.raise_for_status()
                health = health_response.json()
                health_model_name = health.get("model_file") or health.get("model_repo") or ""
                if not _matches_required_model(health_model_name):
                    raise RuntimeError(
                        f"Required model '{_required_model()}' is not active on HF Space. "
                        f"Current model: '{health_model_name or 'unknown'}'."
                    )
            except RuntimeError:
                raise
            except Exception as exc:
                raise RuntimeError(f"Could not verify HF Space model health: {exc}") from exc

        # HF Space contract uses /api/generate and /api/generate_vision.
        prompt = f"{system}\n\n{user}".strip()
        if images:
            payload = {
                "prompt": prompt,
                "image_base64": images[0],
                "model": _hf_model_hint(),
                "max_tokens": 512,
            }
            endpoint = "/api/generate_vision"
        else:
            payload = {
                "prompt": prompt,
                "model": _hf_model_hint(),
                "max_tokens": 512,
            }
            endpoint = "/api/generate"

        try:
            response = httpx.post(
                f"{base_url}{endpoint}",
                json=payload,
                timeout=120.0,
                headers=_headers(),
            )
            response.raise_for_status()
            body = response.json()
            return (
                body.get("response")
                or body.get("text")
                or body.get("output")
                or ""
            ).strip()
        except httpx.TimeoutException as exc:
            raise RuntimeError("HF Space timed out. Is the Space warm?") from exc
        except Exception as exc:
            raise RuntimeError(f"HF Space error: {exc}") from exc

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
            headers=_headers(),
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
    base_url = _normalize_base_url(base_url)
    if base_url.endswith(".hf.space"):
        try:
            response = httpx.get(f"{base_url}/api/health", timeout=5.0, headers=_headers())
            response.raise_for_status()
            health = response.json()
            model_loaded = bool(health.get("model_loaded", False))
            model_name = health.get("model_file") or health.get("model_repo") or "hf-space-model"
            strict_match = _matches_required_model(model_name)
            ready = model_loaded and (strict_match or not _strict_required_model())
            return {
                "ready": ready,
                "model": model_name,
                "all_models": [model_name] if model_loaded else [],
                "ollama_running": True,
                "ollama_url": base_url,
                "required_model": _required_model(),
                "required_model_loaded": strict_match,
            }
        except Exception:
            return {
                "ready": False,
                "model": None,
                "all_models": [],
                "ollama_running": False,
                "ollama_url": base_url,
                "required_model": _required_model(),
                "required_model_loaded": False,
            }

    try:
        response = httpx.get(f"{base_url}/api/tags", timeout=3.0, headers=_headers())
        models = [model["name"] for model in response.json().get("models", [])]
        model = resolve_model(base_url)
        return {
            "ready": model is not None,
            "model": model or "none",
            "all_models": models,
            "ollama_running": True,
            "ollama_url": base_url,
            "required_model": _required_model(),
            "required_model_loaded": model is not None,
        }
    except Exception:
        return {
            "ready": False,
            "model": None,
            "all_models": [],
            "ollama_running": False,
            "ollama_url": base_url,
            "required_model": _required_model(),
            "required_model_loaded": False,
        }

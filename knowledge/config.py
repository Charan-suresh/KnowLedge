import os
from pathlib import Path

import httpx

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_APP_BASE_URL = "http://localhost:8000"


def _env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)).strip())
    except Exception:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)).strip())
    except Exception:
        return default


def _env_str(name: str, default: str = "") -> str:
    return (os.getenv(name, default) or default).strip()


def _normalize_backend(value: str) -> str:
    backend = (value or "hf_space").strip().lower()
    if backend in {"huggingface", "hf", "hfspace"}:
        return "hf_space"
    return backend or "hf_space"


def _env_ollama_base_url() -> str:
    configured = _env_str("OLLAMA_BASE_URL") or _env_str("OLLAMA_URL") or DEFAULT_OLLAMA_BASE_URL
    return configured.rstrip("/") or DEFAULT_OLLAMA_BASE_URL


def _normalize_hf_space_url(value: str) -> str:
    configured = (value or "").strip().rstrip("/")
    if configured.startswith("https://huggingface.co/spaces/"):
        parts = configured.split("/")
        if len(parts) >= 6:
            return f"https://{parts[4]}-{parts[5]}.hf.space"
    return configured


def fetch_ollama_models(base_url: str) -> list[str]:
    try:
        response = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=3.0)
        response.raise_for_status()
        return [model.get("name", "") for model in response.json().get("models", []) if model.get("name")]
    except Exception:
        return []


INFERENCE_BACKEND = _normalize_backend(_env_str("INFERENCE_BACKEND", "hf_space"))
OLLAMA_BASE_URL = _env_ollama_base_url()
OLLAMA_AUTH_TOKEN = _env_str("OLLAMA_AUTH_TOKEN")
HF_SPACE_URL = _normalize_hf_space_url(_env_str("HF_SPACE_URL"))
REQUIRED_MODEL = _env_str("REQUIRED_MODEL", "gemma4:e4b").lower() or "gemma4:e4b"
STRICT_REQUIRED_MODEL = _env_bool("STRICT_REQUIRED_MODEL", True)
DEMO_MODE = _env_bool("DEMO_MODE", False)
DB_PATH = _env_str("DB_PATH", str(BASE_DIR / "data" / "knowledge.db"))
CHROMA_PATH = _env_str("CHROMA_PATH", str(PROJECT_ROOT / "chroma_store"))
APP_BASE_URL = _env_str("APP_BASE_URL", DEFAULT_APP_BASE_URL)
COURSE_ID = _env_str("COURSE_ID", "CS301")
UNIVERSITY_SERVER_URL = _env_str("UNIVERSITY_SERVER_URL")
SYNC_ON_WIFI_ONLY = _env_bool("SYNC_ON_WIFI_ONLY", False)
AUTO_SUBMIT_HOURS = _env_int("AUTO_SUBMIT_HOURS", 24)
SAGE_TIMEOUT_SECONDS = _env_int("SAGE_TIMEOUT_SECONDS", 75)
SOLO_TIMEOUT_SECONDS = _env_int("SOLO_TIMEOUT_SECONDS", 300)
SOCRATIC_INTERRUPT_PROBABILITY = _env_float("SOCRATIC_INTERRUPT_PROBABILITY", 0.15)
LOW_RAM = _env_bool("LOW_RAM", True)
VOICE_MODE = _env_bool("VOICE_MODE", False)
SPOOFED_THRESHOLD = _env_int("SPOOFED_THRESHOLD", 3)
INTEGRITY_VARIANCE_THRESHOLD = _env_float("INTEGRITY_VARIANCE_THRESHOLD", 3.0)
GOOGLE_CLIENT_ID = _env_str("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = _env_str("GOOGLE_CLIENT_SECRET")
GEMINI_API_KEY = _env_str("GEMINI_API_KEY")
SCOUT_MODEL = _env_str("SCOUT_MODEL", "gemma4:e2b")
SAGE_MODEL = _env_str("SAGE_MODEL", "gemma4:e4b")
LENS_MODEL = _env_str("LENS_MODEL", "gemma4:e4b")
DEVICE_KEY_PATH = _env_str("DEVICE_KEY_PATH", str(BASE_DIR / "data" / "device.key"))


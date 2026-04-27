import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"


def _env_ollama_base_url() -> str:
    # Support both names so hosted environments can use either convention.
    configured = (
        os.getenv("OLLAMA_BASE_URL")
        or os.getenv("OLLAMA_URL")
        or DEFAULT_OLLAMA_BASE_URL
    )
    return configured.rstrip("/") or DEFAULT_OLLAMA_BASE_URL


OLLAMA_BASE_URL = _env_ollama_base_url()
OLLAMA_AUTH_TOKEN = os.getenv("OLLAMA_AUTH_TOKEN", "").strip()
REQUIRED_MODEL = (os.getenv("REQUIRED_MODEL") or "gemma4:e4b").strip().lower() or "gemma4:e4b"
STRICT_REQUIRED_MODEL = os.getenv("STRICT_REQUIRED_MODEL", "true").lower() == "true"
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"
DB_PATH = str(BASE_DIR / "data" / "knowledge.db")
INFERENCE_BACKEND = os.getenv("INFERENCE_BACKEND", "ollama").strip().lower()
HF_SPACE_URL = os.getenv("HF_SPACE_URL", "").strip()

# If using huggingface space, and OLLAMA_BASE_URL is not explicitly set, use HF space URL
if INFERENCE_BACKEND == "huggingface" and HF_SPACE_URL and OLLAMA_BASE_URL == DEFAULT_OLLAMA_BASE_URL:
    OLLAMA_BASE_URL = HF_SPACE_URL


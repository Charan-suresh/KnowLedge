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
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"
DB_PATH = str(BASE_DIR / "data" / "knowledge.db")

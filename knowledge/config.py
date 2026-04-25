import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL).rstrip("/") or DEFAULT_OLLAMA_BASE_URL
OLLAMA_AUTH_TOKEN = os.getenv("OLLAMA_AUTH_TOKEN", "").strip()
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"
DB_PATH = str(BASE_DIR / "data" / "knowledge.db")

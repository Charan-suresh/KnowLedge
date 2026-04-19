import os
from pathlib import Path
from typing import Dict, Any, List

import httpx


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent


def _normalize_host(host: str) -> str:
	value = (host or "").strip().rstrip("/")
	return value or "http://localhost:11434"


# Inference
OLLAMA_BASE_URL = _normalize_host(os.getenv("OLLAMA_BASE_URL", os.getenv("OLLAMA_HOST", "http://localhost:11434")))
OLLAMA_AUTH_TOKEN = os.getenv("OLLAMA_AUTH_TOKEN", "")

SCOUT_MODEL = os.getenv("SCOUT_MODEL", "gemma4:e2b")
SAGE_MODEL = os.getenv("SAGE_MODEL", "gemma4:e4b")
LENS_MODEL = os.getenv("LENS_MODEL", "gemma4:e4b")

# Backward compatibility aliases
OLLAMA_HOST = OLLAMA_BASE_URL
SENTINEL_MODEL = SCOUT_MODEL
COLLECTOR_MODEL = SAGE_MODEL
EXAMINER_MODEL = LENS_MODEL

# Storage
DB_PATH = os.getenv("DB_PATH", str(PROJECT_ROOT / "knowledge.db"))
CHROMA_PATH = os.getenv("CHROMA_PATH", str(PROJECT_ROOT / "chroma_store"))

# App
PORT = int(os.getenv("PORT", "8000"))
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
IS_PRODUCTION = ENVIRONMENT == "production"

# Security
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-in-production")

# Google Classroom
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "TODO_SET_YOUR_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "TODO_SET_YOUR_CLIENT_SECRET")
APP_BASE_URL = os.getenv("APP_BASE_URL", f"http://localhost:{PORT}")

# Sync
UNIVERSITY_SERVER_URL = os.getenv("UNIVERSITY_SERVER_URL", "")
COURSE_ID = os.getenv("COURSE_ID", "CS301")
SYNC_ON_WIFI_ONLY = os.getenv("SYNC_ON_WIFI_ONLY", "true").lower() == "true"

# Hackathon demo mode
DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"

# Safety/integrity and timeouts
AUTO_SUBMIT_HOURS = int(os.getenv("AUTO_SUBMIT_HOURS", "24"))
VOICE_MODE = os.getenv("VOICE_MODE", "false").lower() == "true"
SAGE_TIMEOUT_SECONDS = int(os.getenv("SAGE_TIMEOUT_SECONDS", "75"))
SOLO_TIMEOUT_SECONDS = int(os.getenv("SOLO_TIMEOUT_SECONDS", "300"))
LOW_RAM = os.getenv("LOW_RAM", "true").lower() == "true"
SPOOFED_THRESHOLD = int(os.getenv("SPOOFED_THRESHOLD", "3"))
INTEGRITY_VARIANCE_THRESHOLD = float(os.getenv("INTEGRITY_VARIANCE_THRESHOLD", "3.0"))
DEVICE_KEY_PATH = os.getenv("DEVICE_KEY_PATH", "~/.knowledge/device.key")
SOLO_REQUIRES_VOICE_OR_LENS = os.getenv("SOLO_REQUIRES_VOICE_OR_LENS", "true").lower() == "true"


def get_runtime_llm_config() -> Dict[str, str]:
	return {
		"ollama_base_url": OLLAMA_BASE_URL,
		"ollama_host": OLLAMA_BASE_URL,
		"scout_model": SCOUT_MODEL,
		"sage_model": SAGE_MODEL,
		"lens_model": LENS_MODEL,
	}


def set_runtime_llm_config(
	ollama_base_url: str,
	scout_model: str,
	sage_model: str,
	lens_model: str,
) -> Dict[str, str]:
	global OLLAMA_BASE_URL, OLLAMA_HOST, SCOUT_MODEL, SAGE_MODEL, LENS_MODEL
	global SENTINEL_MODEL, COLLECTOR_MODEL, EXAMINER_MODEL

	OLLAMA_BASE_URL = _normalize_host(ollama_base_url)
	OLLAMA_HOST = OLLAMA_BASE_URL
	SCOUT_MODEL = (scout_model or "").strip() or SCOUT_MODEL
	SAGE_MODEL = (sage_model or "").strip() or SAGE_MODEL
	LENS_MODEL = (lens_model or "").strip() or LENS_MODEL

	SENTINEL_MODEL = SCOUT_MODEL
	COLLECTOR_MODEL = SAGE_MODEL
	EXAMINER_MODEL = LENS_MODEL
	return get_runtime_llm_config()


def load_runtime_llm_config(saved: Dict[str, Any]) -> Dict[str, str]:
	if not saved:
		return get_runtime_llm_config()
	return set_runtime_llm_config(
		ollama_base_url=saved.get("ollama_base_url", saved.get("ollama_host", OLLAMA_BASE_URL)),
		scout_model=saved.get("scout_model", SCOUT_MODEL),
		sage_model=saved.get("sage_model", SAGE_MODEL),
		lens_model=saved.get("lens_model", LENS_MODEL),
	)


def fetch_ollama_models(host: str = "") -> List[str]:
	target = _normalize_host(host or OLLAMA_BASE_URL)
	headers = {"Authorization": f"Bearer {OLLAMA_AUTH_TOKEN}"} if OLLAMA_AUTH_TOKEN else {}
	try:
		response = httpx.get(f"{target}/api/tags", timeout=6.0, headers=headers)
		response.raise_for_status()
		models = response.json().get("models", [])
		names = [m.get("name", "") for m in models if m.get("name")]
		return sorted(names)
	except Exception:
		return []

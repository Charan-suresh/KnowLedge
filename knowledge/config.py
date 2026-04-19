import os
from typing import Dict, Any, List

import httpx


def _normalize_host(host: str) -> str:
	value = (host or "").strip().rstrip("/")
	return value or "http://localhost:11434"


DEFAULT_OLLAMA_HOST = _normalize_host(os.getenv("OLLAMA_HOST", "http://localhost:11434"))

# Model Configuration (KnowLedge naming)
SCOUT_MODEL = os.getenv("SCOUT_MODEL", "gemma4:e2b")   # was SENTINEL_MODEL
SAGE_MODEL  = os.getenv("SAGE_MODEL",  "gemma4:e4b")   # was COLLECTOR_MODEL
LENS_MODEL  = os.getenv("LENS_MODEL",  "gemma4:e4b")   # was EXAMINER_MODEL
OLLAMA_HOST = DEFAULT_OLLAMA_HOST

# Legacy aliases (keep until all code is migrated)
SENTINEL_MODEL = SCOUT_MODEL
COLLECTOR_MODEL = SAGE_MODEL
EXAMINER_MODEL = LENS_MODEL

# Database Configuration
DB_PATH = os.getenv("DB_PATH", "debt_log.db")

# Vector Store Configuration
CHROMA_PATH = os.getenv("CHROMA_PATH", "./cdt_vectorstore")

# Hardware Constraints
LOW_RAM = os.getenv("LOW_RAM", "true").lower() == "true"

# ── Google Classroom Add-on ────────────────────────────────────────────────────
# TODO: Set these in your environment or a .env file before deploying.
GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "TODO_SET_YOUR_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "TODO_SET_YOUR_CLIENT_SECRET")

# The public HTTPS base URL of this app (required for OAuth redirect URIs).
# For local dev: run `ngrok http 8501` and paste the https URL here.
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8501")

# Safety valve: hours before auto-submitting if student hasn't cleared Sage
AUTO_SUBMIT_HOURS = int(os.getenv("AUTO_SUBMIT_HOURS", "24"))

# Sync
UNIVERSITY_SERVER_URL = os.getenv("UNIVERSITY_SERVER_URL", "https://knowledge.youruniversity.edu/aggregate")
COURSE_ID = os.getenv("COURSE_ID", "CS301")
SYNC_ON_WIFI_ONLY = os.getenv("SYNC_ON_WIFI_ONLY", "true").lower() == "true"

# Anti-gaming
VOICE_MODE = os.getenv("VOICE_MODE", "false").lower() == "true"
SAGE_TIMEOUT_SECONDS = int(os.getenv("SAGE_TIMEOUT_SECONDS", "75"))
SOLO_TIMEOUT_SECONDS = int(os.getenv("SOLO_TIMEOUT_SECONDS", "300"))
SPOOFED_THRESHOLD = int(os.getenv("SPOOFED_THRESHOLD", "3"))
INTEGRITY_VARIANCE_THRESHOLD = float(os.getenv("INTEGRITY_VARIANCE_THRESHOLD", "3.0"))
DEVICE_KEY_PATH = os.getenv("DEVICE_KEY_PATH", "~/.knowledge/device.key")

# Solo Mode
SOLO_REQUIRES_VOICE_OR_LENS = os.getenv("SOLO_REQUIRES_VOICE_OR_LENS", "true").lower() == "true"


def get_runtime_llm_config() -> Dict[str, str]:
	return {
		"ollama_host": OLLAMA_HOST,
		"scout_model": SCOUT_MODEL,
		"sage_model": SAGE_MODEL,
		"lens_model": LENS_MODEL,
	}


def set_runtime_llm_config(
	ollama_host: str,
	scout_model: str,
	sage_model: str,
	lens_model: str,
) -> Dict[str, str]:
	global OLLAMA_HOST, SCOUT_MODEL, SAGE_MODEL, LENS_MODEL
	global SENTINEL_MODEL, COLLECTOR_MODEL, EXAMINER_MODEL

	OLLAMA_HOST = _normalize_host(ollama_host)
	SCOUT_MODEL = (scout_model or "").strip() or SCOUT_MODEL
	SAGE_MODEL = (sage_model or "").strip() or SAGE_MODEL
	LENS_MODEL = (lens_model or "").strip() or LENS_MODEL

	# Keep legacy aliases aligned with runtime values.
	SENTINEL_MODEL = SCOUT_MODEL
	COLLECTOR_MODEL = SAGE_MODEL
	EXAMINER_MODEL = LENS_MODEL
	return get_runtime_llm_config()


def load_runtime_llm_config(saved: Dict[str, Any]) -> Dict[str, str]:
	if not saved:
		return get_runtime_llm_config()
	return set_runtime_llm_config(
		ollama_host=saved.get("ollama_host", OLLAMA_HOST),
		scout_model=saved.get("scout_model", SCOUT_MODEL),
		sage_model=saved.get("sage_model", SAGE_MODEL),
		lens_model=saved.get("lens_model", LENS_MODEL),
	)


def fetch_ollama_models(host: str = "") -> List[str]:
	target = _normalize_host(host or OLLAMA_HOST)
	try:
		response = httpx.get(f"{target}/api/tags", timeout=4.0)
		response.raise_for_status()
		models = response.json().get("models", [])
		names = [m.get("name", "") for m in models if m.get("name")]
		return sorted(names)
	except Exception:
		return []

import hashlib
import hmac
import json
import os
import statistics
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

from .. import config


def _device_secret() -> bytes:
    key_path = Path(os.path.expanduser(config.DEVICE_KEY_PATH))
    key_path.parent.mkdir(parents=True, exist_ok=True)
    if not key_path.exists():
        key_path.write_text(os.urandom(32).hex(), encoding="utf-8")
    return key_path.read_text(encoding="utf-8").strip().encode("utf-8")


def _extract_response_times(chat_history: List[Dict[str, Any]]) -> List[float]:
    times: List[float] = []
    for msg in chat_history:
        meta = msg.get("meta", {}) if isinstance(msg, dict) else {}
        rt = meta.get("response_time_seconds")
        if isinstance(rt, (int, float)) and rt >= 0:
            times.append(float(rt))
    return times


def _extract_lengths(chat_history: List[Dict[str, Any]]) -> List[int]:
    lengths: List[int] = []
    for msg in chat_history:
        if isinstance(msg, dict) and msg.get("role") == "user":
            lengths.append(len((msg.get("content") or "").strip()))
    return lengths


def build_session_fingerprint(session_id: str, concept: str, chat_history: List[Dict[str, Any]], started_at: datetime | None = None, ended_at: datetime | None = None) -> Dict[str, Any]:
    start = started_at or datetime.utcnow()
    end = ended_at or datetime.utcnow()
    duration = max(0, int((end - start).total_seconds()))

    response_times = _extract_response_times(chat_history)
    response_lengths = _extract_lengths(chat_history)
    paste_detected = any((m.get("meta", {}) or {}).get("paste_detected") for m in chat_history if isinstance(m, dict))
    backspace_events = sum(int((m.get("meta", {}) or {}).get("backspace_events", 0)) for m in chat_history if isinstance(m, dict))
    timeout_count = sum(1 for t in response_times if t >= config.SAGE_TIMEOUT_SECONDS)

    median_rt = statistics.median(response_times) if response_times else 0.0
    variance_rt = statistics.pvariance(response_times) if len(response_times) > 1 else 0.0

    return {
        "session_id": session_id,
        "concept": concept,
        "total_duration_seconds": duration,
        "turn_count": len([m for m in chat_history if isinstance(m, dict) and m.get("role") == "user"]),
        "response_times": response_times,
        "response_lengths": response_lengths,
        "timeout_count": timeout_count,
        "median_response_time": float(median_rt),
        "response_time_variance": float(variance_rt),
        "backspace_events": backspace_events,
        "paste_detected": bool(paste_detected),
        "language_detected": "en",
    }


def _fingerprint_canonical(fp: Dict[str, Any]) -> str:
    stable = {
        "session_id": fp.get("session_id"),
        "concept": fp.get("concept"),
        "total_duration_seconds": fp.get("total_duration_seconds", 0),
        "turn_count": fp.get("turn_count", 0),
        "response_times": fp.get("response_times", []),
        "response_lengths": fp.get("response_lengths", []),
        "timeout_count": fp.get("timeout_count", 0),
        "median_response_time": fp.get("median_response_time", 0.0),
        "response_time_variance": fp.get("response_time_variance", 0.0),
        "backspace_events": fp.get("backspace_events", 0),
        "paste_detected": bool(fp.get("paste_detected", False)),
        "language_detected": fp.get("language_detected", "unknown"),
    }
    return json.dumps(stable, separators=(",", ":"), sort_keys=True)


def sign_fingerprint(fp: Dict[str, Any]) -> str:
    msg = _fingerprint_canonical(fp).encode("utf-8")
    return hmac.new(_device_secret(), msg, hashlib.sha256).hexdigest()


def verify_session_hash(fp: Dict[str, Any], session_hash: str) -> bool:
    expected = sign_fingerprint(fp)
    return hmac.compare_digest(expected, session_hash or "")

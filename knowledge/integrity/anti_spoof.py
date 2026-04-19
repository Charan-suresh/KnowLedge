import hashlib
from typing import Dict, Any, List

from .. import config


def analyze_integrity(fingerprint: Dict[str, Any]) -> Dict[str, Any]:
    reasons: List[str] = []
    spoof_attempts = 0

    variance = float(fingerprint.get("response_time_variance", 0.0) or 0.0)
    median_rt = float(fingerprint.get("median_response_time", 0.0) or 0.0)
    timeout_count = int(fingerprint.get("timeout_count", 0) or 0)
    paste_detected = bool(fingerprint.get("paste_detected", False))
    turns = int(fingerprint.get("turn_count", 0) or 0)

    if paste_detected:
        reasons.append("paste_detected")
        spoof_attempts += 1
    if timeout_count >= config.SPOOFED_THRESHOLD:
        reasons.append("too_many_timeouts")
        spoof_attempts += 1
    if turns > 0 and median_rt < 0.8:
        reasons.append("unusually_fast_responses")
        spoof_attempts += 1
    if variance > config.INTEGRITY_VARIANCE_THRESHOLD * 10:
        reasons.append("abnormal_response_variance")
        spoof_attempts += 1

    return {
        "integrity_suspect": spoof_attempts > 0,
        "spoof_attempts": spoof_attempts,
        "reasons": reasons,
    }


def make_lens_signature(image_bytes: bytes, explanation: str) -> str:
    digest = hashlib.sha256()
    digest.update(image_bytes)
    digest.update((explanation or "").encode("utf-8"))
    return digest.hexdigest()


def verify_lens_signature(stored_signature: str, image_bytes: bytes, explanation: str) -> bool:
    if not stored_signature:
        return False
    return stored_signature == make_lens_signature(image_bytes, explanation)

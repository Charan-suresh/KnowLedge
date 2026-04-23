import json
import random
import statistics
from typing import Any, Dict, Optional

from .. import config
from ..agents.inference_router import chat

SCORE_WEIGHTS = {
    "paste": 0.45,
    "first_key": 0.20,
    "cadence": 0.20,
    "edit": 0.15,
}

COMPREHENSION_WEIGHTS = {
    "temporal": 0.25,
    "direct_answer": 0.25,
    "probe_depth": 0.30,
    "trap": 0.20,
}

PASTE_LONG_RESPONSE_THRESHOLD = 80
PASTE_LONG_RESPONSE_MAX_SCORE = 0.1
FAST_FIRST_KEY_THRESHOLD_MS = 2000
ZERO_VARIANCE_EPSILON = 1e-9
LONG_RESPONSE_EDIT_CHECK_THRESHOLD = 120
LOW_EDIT_RATIO_THRESHOLD = 0.05

PROBE_STRATEGIES = (
    "SCALE_PROBE",
    "SPECIFICITY_PROBE",
    "WRONG_TRAP",
    "COMPRESSION_PROBE",
)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def score_temporal_fingerprint(fingerprint: Dict[str, Any]) -> float:
    return score_temporal_fingerprint_with_breakdown(fingerprint)["score"]


def score_temporal_fingerprint_with_breakdown(fingerprint: Dict[str, Any]) -> Dict[str, Any]:
    fp = fingerprint or {}
    response_length = int(fp.get("response_length", 0) or 0)
    is_paste = bool(fp.get("is_paste_detected", False))
    time_to_first = float(fp.get("time_to_first_keystroke", 0) or 0)
    cadence = fp.get("typing_cadence", []) or []
    cadence = [float(x) for x in cadence if isinstance(x, (int, float)) and float(x) >= 0]
    edit_ratio = float(fp.get("edit_ratio", 1.0) or 1.0)
    is_complex = bool(fp.get("is_complex_question", False)) or fp.get("question_complexity") == "complex"

    paste_subscore = 0.0 if is_paste else 1.0

    first_key_subscore = 1.0
    if is_complex and time_to_first < FAST_FIRST_KEY_THRESHOLD_MS:
        first_key_subscore = 0.25

    cadence_subscore = 1.0
    cadence_variance = 0.0
    if len(cadence) >= 2:
        cadence_variance = statistics.pvariance(cadence)
        if cadence_variance <= ZERO_VARIANCE_EPSILON:
            cadence_subscore = 0.2
    elif response_length > 60:
        cadence_subscore = 0.5

    edit_subscore = 1.0
    if response_length >= LONG_RESPONSE_EDIT_CHECK_THRESHOLD and edit_ratio < LOW_EDIT_RATIO_THRESHOLD:
        edit_subscore = 0.2
    elif response_length >= LONG_RESPONSE_EDIT_CHECK_THRESHOLD and edit_ratio > 0.98:
        # Very linear long answers can indicate pasted relay even when paste event is missed.
        edit_subscore = 0.35

    weighted_score = (
        SCORE_WEIGHTS["paste"] * paste_subscore
        + SCORE_WEIGHTS["first_key"] * first_key_subscore
        + SCORE_WEIGHTS["cadence"] * cadence_subscore
        + SCORE_WEIGHTS["edit"] * edit_subscore
    )

    if is_paste and response_length > PASTE_LONG_RESPONSE_THRESHOLD:
        weighted_score = min(weighted_score, PASTE_LONG_RESPONSE_MAX_SCORE)

    score = _clamp01(weighted_score)
    return {
        "score": score,
        "components": {
            "paste_subscore": paste_subscore,
            "first_key_subscore": first_key_subscore,
            "cadence_subscore": cadence_subscore,
            "edit_subscore": edit_subscore,
            "cadence_variance": cadence_variance,
        },
        "inputs": {
            "is_paste_detected": is_paste,
            "response_length": response_length,
            "time_to_first_keystroke": time_to_first,
            "is_complex_question": is_complex,
            "edit_ratio": edit_ratio,
            "typing_cadence_samples": len(cadence),
        },
    }


def compute_true_comprehension(
    direct_answer_score: float,
    temporal_score: float,
    probe_depth_score: float,
    trap_score: float,
) -> float:
    composite = (
        COMPREHENSION_WEIGHTS["temporal"] * _clamp01(temporal_score)
        + COMPREHENSION_WEIGHTS["direct_answer"] * _clamp01(direct_answer_score)
        + COMPREHENSION_WEIGHTS["probe_depth"] * _clamp01(probe_depth_score)
        + COMPREHENSION_WEIGHTS["trap"] * _clamp01(trap_score)
    )
    return round(_clamp01(composite), 4)


def derive_comprehension_status(true_comprehension: float, diagram_verified: bool = False) -> str:
    value = _clamp01(true_comprehension)
    if value < 0.4:
        return "live_session_required"
    if value < 0.6:
        return "verified" if diagram_verified else "unverified"
    if value < 0.8:
        return "shallow"
    return "verified"


def pick_probe_strategy(student_response: str, difficulty: str) -> str:
    text = (student_response or "").strip()
    lowered = text.lower()

    if difficulty.lower() in {"hard", "advanced"} and len(text) < 120:
        return "SCALE_PROBE"
    if len(text) < 70:
        return "SPECIFICITY_PROBE"
    if any(tok in lowered for tok in ("i think", "maybe", "kind of", "sort of")):
        return "SPECIFICITY_PROBE"

    # Keep wrong-trap occasional to avoid making interactions feel adversarial.
    if random.random() < 0.2:
        return "WRONG_TRAP"
    if random.random() < 0.35:
        return "COMPRESSION_PROBE"
    return "SCALE_PROBE"


def generate_probe(
    student_response: str,
    concept: str,
    artifact_context: Optional[str],
    difficulty: str,
    strategy: Optional[str] = None,
) -> Dict[str, str]:
    chosen_strategy = strategy or pick_probe_strategy(student_response, difficulty)
    if chosen_strategy not in PROBE_STRATEGIES:
        chosen_strategy = "SPECIFICITY_PROBE"

    artifact_block = ""
    if artifact_context and artifact_context.strip():
        artifact_block = f"\nArtifact context from student work:\n{artifact_context.strip()}\n"

    strategy_directives = {
        "SCALE_PROBE": "Change one concrete constraint (size, speed, edge or failure case) and ask how their answer changes.",
        "SPECIFICITY_PROBE": "Ask about a detail from the student's exact wording or artifact, not generic theory.",
        "WRONG_TRAP": "State one subtly incorrect claim about the concept and ask the student to react. Keep it plausible.",
        "COMPRESSION_PROBE": "Ask the student to explain to a non-technical person in 2 sentences max.",
    }

    system_prompt = (
        "You are Sage, a warm Socratic tutor. Generate exactly ONE follow-up probe question and nothing else. "
        "Do not answer the question yourself. Keep it under 35 words.\n"
        f"Probe strategy: {chosen_strategy}\n"
        f"Strategy instruction: {strategy_directives[chosen_strategy]}\n"
        f"Concept: {concept}\n"
        f"Student response:\n{(student_response or '').strip()}\n"
        f"Difficulty: {difficulty}\n"
        f"{artifact_block}"
    )

    response = chat(
        model=config.SAGE_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Return one probe question only."},
        ],
    )
    question = (response.get("message", {}) or {}).get("content", "").strip()
    if not question:
        question = "Can you walk me through one concrete example from your own solution?"

    question = question.replace("\n", " ").strip().strip('"')
    if not question.endswith("?"):
        question = f"{question.rstrip('.')}?"

    return {
        "probe": question,
        "strategy": chosen_strategy,
    }


def serialize_payload(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True)

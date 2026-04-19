import json
from typing import Dict, Any

import ollama

from . import config
from .retrieval import build_context


def evaluate_real_learning(concept: str, question: str, response: str) -> Dict[str, Any]:
    context = build_context(concept)
    eval_prompt = f"""
You are a strict evaluator.
Concept: {concept}
Question: {question}
Student response: {response}
Reference context: {context}

Return JSON only with keys:
- score (0-100)
- reasoning (string)
- specific_gaps (array of strings)
"""
    try:
        client = ollama.Client(host=config.OLLAMA_HOST)
        out = client.chat(
            model=config.SAGE_MODEL,
            messages=[{"role": "user", "content": eval_prompt}],
            format="json",
        )
        raw = out.get("message", {}).get("content", "{}")
        parsed = json.loads(raw)
        score = int(parsed.get("score", 0))
        score = max(0, min(100, score))
        return {
            "score": score,
            "reasoning": parsed.get("reasoning", ""),
            "specific_gaps": parsed.get("specific_gaps", []),
        }
    except Exception:
        # Fallback keeps feature functional when evaluator model is unavailable.
        heuristic_score = min(100, max(0, len((response or "").split()) * 4))
        return {
            "score": heuristic_score,
            "reasoning": "Fallback scoring used due to evaluator unavailability.",
            "specific_gaps": ["Evaluation model unavailable"],
        }

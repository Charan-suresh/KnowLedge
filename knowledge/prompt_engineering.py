import json
from typing import List

from . import config
from .agents.ollama_client import chat


def generate_solo_question(concept: str, prior_questions: List[str]) -> str:
    prior = "\n".join(f"- {q}" for q in prior_questions[:10]) if prior_questions else "- none"
    prompt = f"""
You are generating one strict solo assessment question for the concept: {concept}.
Rules:
- Do not repeat or paraphrase prior questions.
- Target reasoning, not memorization.
- Keep it answerable in 3-6 sentences.
Prior questions:
{prior}
Return only the question text.
"""
    try:
        resp = chat(
            model=config.SAGE_MODEL,
            messages=[
                {"role": "system", "content": "You create concise, novel assessment questions."},
                {"role": "user", "content": prompt},
            ],
        )
        question = (resp.get("message", {}).get("content", "") or "").strip()
        return question or f"Explain {concept} in your own words and justify each step."
    except Exception:
        return f"Explain {concept} in your own words and justify each step."

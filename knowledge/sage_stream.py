"""
sage_stream.py
Async generator that streams Sage (Gemma 4 E4B) token-by-token via Ollama.
Used by the SSE endpoint to deliver live responses inside the Classroom iframe
and the standalone ledger Sage modal.

RAG: pulls relevant curriculum context from ChromaDB (US Curriculum Guide)
to ground Sage's Socratic questions in real course material.
"""

import asyncio
import re
from typing import AsyncGenerator, Optional
from . import db
from . import config
from .agents.inference_router import stream_chat

# RAG retrieval — gracefully skipped if vectorstore not ready
try:
    from .retrieval import build_context as _rag_build_context
    RAG_AVAILABLE = True
except Exception:
    RAG_AVAILABLE = False


_ROLE_TAG_RE = re.compile(r"\*\*\[(SYSTEM|USER|ASSISTANT)\]\*\*|\[(SYSTEM|USER|ASSISTANT)\]", re.IGNORECASE)


def _enforce_socratic_question(reply: str) -> str:
    """
    Ensure Sage returns one clean Socratic question only.
    - Removes leaked role tags and transcript artifacts.
    - Strips explanation preambles ("Atoms bond because...") to find the actual question.
    - Prefers the first sentence that ends with '?'.
    - Falls back to a safe probing question.
    """
    cleaned = _ROLE_TAG_RE.sub("", (reply or ""))
    cleaned = cleaned.replace("Assistant:", "").replace("User:", "").replace("System instructions:", "")
    cleaned = " ".join(cleaned.split())

    if "CLEARED" in cleaned.upper():
        return "CLEARED"

    # Split into sentences and find questions that look Socratic (not restatement requests).
    sentences = re.split(r"(?<=[?.!])\s+", cleaned)
    
    # Scan through sentences looking for legitimate Socratic questions.
    # Prefer questions that ask about understanding, definitions, implications, etc.
    # Skip generic restatement requests like "Can you explain that in your own words?"
    socratic_keywords = {
        "what", "why", "how", "which", "where", "when", "could", 
        "would", "should", "difference", "example", "means", "describe",
        "think", "consider", "tell", "show", "compare"
    }
    
    # Phrases that indicate non-Socratic restatement questions.
    avoid_phrases = {"explain that", "restate", "rephrase", "say that", "put that", "describe that"}
    
    for part in sentences:
        segment = part.strip()
        if not (segment.endswith("?") and len(segment) > 8):
            continue
        
        lower = segment.lower()
        # Skip restatement requests.
        if any(phrase in lower for phrase in avoid_phrases):
            continue
        
        # Prefer questions with Socratic keywords.
        if any(keyword in lower for keyword in socratic_keywords):
            return segment
    
    # If no Socratic-looking question found, check remaining questions but skip restatement ones.
    for part in sentences:
        segment = part.strip()
        if not (segment.endswith("?") and len(segment) > 8):
            continue
        lower = segment.lower()
        if not any(phrase in lower for phrase in avoid_phrases):
            return segment

    # Final fallback: a genuine Socratic question.
    return "What do you know about this concept? Can you give me an example?"


def _build_system_prompt(concept: str, debt_entries: list) -> str:
    """
    Builds Sage's system prompt with two context sources:
      1. Curriculum context — top-k chunks from the US Curriculum Guide vectorstore
      2. Student notes context — the student's own source_text from debt_log
    """
    # ── 1. Curriculum RAG context ──────────────────────────────────────────────
    curriculum_context = ""
    if RAG_AVAILABLE:
        try:
            curriculum_context = _rag_build_context(concept)
        except Exception:
            curriculum_context = ""

    # ── 2. Student debt entries ────────────────────────────────────────────────
    student_notes = "\n".join(
        [f"- {e['source_text'][:150]}" for e in debt_entries[:3] if e.get("source_text")]
    )

    curriculum_block = (
        f"\nCurriculum reference (US Curriculum Guide):\n{curriculum_context}\n"
        if curriculum_context.strip()
        else ""
    )
    notes_block = (
        f"\nStudent's prior notes:\n{student_notes}\n"
        if student_notes.strip()
        else ""
    )

    return f"""You are Sage, a Socratic tutor embedded inside a Google Classroom assignment. \
Your only job is to ask probing questions — never explain the answer yourself.

The student needs to demonstrate genuine understanding of: "{concept}".
{curriculum_block}{notes_block}
Rules:
- Ask exactly ONE focused question per turn.
- If the student's answer is vague or uses jargon without explanation, probe deeper with a follow-up.
- If they demonstrate clear, genuine understanding in their own words, respond with exactly: CLEARED
- Never give the answer away. Only ask questions.
- Keep questions grounded in the curriculum context above when available."""


async def run_sage_ollama(
    session_id: str,
    chat_history: list[dict],
    concept: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """
    Streams Sage's reply token-by-token.
    Yields plain string tokens; caller wraps in SSE `data: {...}` format.

    Concept resolution priority:
      1. `concept` kwarg (passed directly from the ledger modal)
      2. classroom_session.assignment_id (for Classroom iframe flow)
      3. Fallback to "the concept"
    """
    if concept is None:
        session = db.get_classroom_session(session_id)
        concept = (session or {}).get("assignment_id", "the concept")

    debt_entries = db.get_debt_by_concept(concept)
    system_prompt = _build_system_prompt(concept, debt_entries)
    messages = [{"role": "system", "content": system_prompt}] + chat_history

    full_reply = ""
    emitted_question = False
    try:
        async for chunk in stream_chat(model=config.SAGE_MODEL, messages=messages):
            token = chunk.get("message", {}).get("content", "")
            full_reply += token

            if emitted_question:
                continue

            # Emit early as soon as we can confidently form one focused question.
            normalized = _enforce_socratic_question(full_reply)
            if normalized == "CLEARED":
                yield "CLEARED"
                yield "\n__CLEARED__"
                return

            if normalized.endswith("?") and len(normalized) > 8:
                yield normalized
                emitted_question = True

        if not emitted_question:
            normalized = _enforce_socratic_question(full_reply)
            if normalized == "CLEARED":
                yield "CLEARED"
                yield "\n__CLEARED__"
                return
            if normalized:
                yield normalized

        # Signal clearing to the SSE wrapper
        if "CLEARED" in full_reply.upper():
            yield "\n__CLEARED__"

    except Exception as e:
        err_str = str(e)
        err_type = type(e).__name__

        # Missing configuration
        if "HF_SPACE_URL" in err_str:
            yield (
                "\n[Sage error: Inference backend is not configured. "
                "Please set the HF_SPACE_URL environment variable on Render.]"
            )
        # HF Space cold-start / connection refused
        elif (
            "ConnectError" in err_type
            or "connect" in err_str.lower()
            or "Connection refused" in err_str
            or "Could not get Gradio config" in err_str
        ):
            yield (
                "\n[Sage error: Could not reach the Hugging Face inference Space. "
                "The Space may be waking up from sleep — please wait 20–30 seconds and try again.]"
            )
        # Timeout during model loading or generation
        elif "timeout" in err_str.lower() or "Timeout" in err_type or "ReadTimeout" in err_type:
            yield (
                "\n[Sage error: The inference request timed out. "
                "Gemma 4 may still be loading on the GPU — please try again in a moment.]"
            )
        # HF Space returned an HTTP error (e.g. 503 while waking)
        elif "HTTPStatusError" in err_type or "status code" in err_str.lower():
            yield (
                "\n[Sage error: The inference Space returned an error. "
                "It may be overloaded or restarting — please try again shortly.]"
            )
        else:
            yield f"\n[Sage error: {e}]"

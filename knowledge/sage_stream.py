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


def _build_history_block(chat_history: list[dict]) -> str:
    """Format prior turns as [PRIOR CONVERSATION] block."""
    turns = []
    idx = 1
    i = 0
    while i < len(chat_history) - 1:
        msg, nxt = chat_history[i], chat_history[i + 1]
        role = (msg.get("role") or "").lower()
        nxt_role = (nxt.get("role") or "").lower()
        if role in {"assistant", "sage"} and nxt_role in {"user", "student"}:
            q = (msg.get("content") or "").strip()
            a = (nxt.get("content") or "").strip()
            if q and a:
                turns.append(f"Turn {idx} - Sage: {q}")
                turns.append(f"Turn {idx} - Student: {a}")
                idx += 1
            i += 2
        else:
            i += 1
    if not turns:
        return ""
    return "[PRIOR CONVERSATION]\n" + "\n".join(turns) + "\n[END PRIOR CONVERSATION]"


def _clean_reply(reply: str) -> str:
    """Strip role tags, XML-like format tags, and normalize whitespace."""
    cleaned = _ROLE_TAG_RE.sub("", (reply or ""))
    # Strip any literal format tags the model may have output
    cleaned = re.sub(r"</?(?:explanation|question|answer|response)>", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace("Assistant:", "").replace("User:", "").replace("System instructions:", "")
    # Collapse runs of whitespace but preserve single newlines between sentences
    cleaned = re.sub(r" {2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _format_sage_response(reply: str) -> str:
    """
    Parses Sage's raw reply into: <explanation>\n\n<question>
    The model is NOT told to use tags — we split on the last sentence
    ending with '?' and treat everything before it as the explanation.
    """
    cleaned = _clean_reply(reply)

    if not cleaned:
        return "Can you walk me through one concrete example of this concept?"
    if "CLEARED" in cleaned.upper():
        return "CLEARED"

    # Split into sentences preserving structure
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", cleaned) if s.strip()]

    # Find the LAST question sentence — that's the probe
    question_idx = None
    for i in range(len(sentences) - 1, -1, -1):
        if sentences[i].endswith("?") and len(sentences[i]) > 8:
            question_idx = i
            break

    if question_idx is None:
        # No question found — return as-is (model may have given explanation only)
        return cleaned

    explanation = " ".join(sentences[:question_idx]).strip()
    question = sentences[question_idx]

    if explanation:
        return explanation + "\n\n" + question
    return question


def _build_system_prompt(concept: str, debt_entries: list, history_block: str = "") -> str:
    """
    Builds Sage's system prompt with two context sources:
      1. Curriculum context — top-k chunks from the US Curriculum Guide vectorstore
      2. Student notes context — the student's own source_text from debt_log
    """
    curriculum_context = ""
    if RAG_AVAILABLE:
        try:
            curriculum_context = _rag_build_context(concept)
        except Exception:
            curriculum_context = ""

    student_notes = "\n".join(
        [f"- {e['source_text'][:150]}" for e in debt_entries[:3] if e.get("source_text")]
    )

    curriculum_block = (
        f"\nCurriculum reference:\n{curriculum_context}\n"
        if curriculum_context.strip() else ""
    )
    notes_block = (
        f"\nStudent's prior notes:\n{student_notes}\n"
        if student_notes.strip() else ""
    )
    no_repeat = (
        f"\n{history_block}\nYou have already asked the questions above. "
        "Do NOT repeat or rephrase any of them. Your next response must probe a NEW aspect.\n"
        if history_block else ""
    )

    return f"""You are Sage, a Socratic tutor. The student is working on: "{concept}".
{curriculum_block}{notes_block}{no_repeat}
Each response must do two things in order:
- First, acknowledge or briefly clarify what the student said (1 sentence).
- Then, ask exactly one focused follow-up question probing a new aspect.

Rules:
- Never repeat or rephrase a question already asked.
- Never reveal the full answer.
- If the student has clearly demonstrated genuine understanding of all key aspects, respond with only the word: CLEARED
- Keep the total response under 50 words."""


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
    history_block = _build_history_block(chat_history[-12:])
    system_prompt = _build_system_prompt(concept, debt_entries, history_block)
    messages = [{"role": "system", "content": system_prompt}] + chat_history

    full_reply = ""
    emitted = False
    try:
        async for chunk in stream_chat(model=config.SAGE_MODEL, messages=messages):
            token = chunk.get("message", {}).get("content", "")
            full_reply += token
            if emitted:
                continue
            # Wait for a complete response (explanation + question) before emitting
            formatted = _format_sage_response(full_reply)
            if formatted == "CLEARED":
                yield "CLEARED"
                yield "\n__CLEARED__"
                return
            # Emit once we have at least one complete sentence ending with ?
            if "?" in formatted and formatted.strip().endswith("?"):
                yield formatted
                emitted = True

        if not emitted:
            formatted = _format_sage_response(full_reply)
            if formatted == "CLEARED":
                yield "CLEARED"
                yield "\n__CLEARED__"
                return
            if formatted:
                yield formatted

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

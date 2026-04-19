"""
sage_stream.py
Async generator that streams Sage (Gemma 4 E4B) token-by-token via Ollama.
Used by the SSE endpoint to deliver live responses inside the Classroom iframe
and the standalone ledger Sage modal.

RAG: pulls relevant curriculum context from ChromaDB (US Curriculum Guide)
to ground Sage's Socratic questions in real course material.
"""

import asyncio
from typing import AsyncGenerator, Optional
from . import db
from . import config

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

# RAG retrieval — gracefully skipped if vectorstore not ready
try:
    from .retrieval import build_context as _rag_build_context
    RAG_AVAILABLE = True
except Exception:
    RAG_AVAILABLE = False


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

    if not OLLAMA_AVAILABLE:
        # Dev fallback — simulate streaming without Ollama
        mock = (
            f"Let's explore **{concept}**. "
            "Can you explain it to me as if I've never encountered it before?"
        )
        for word in mock.split():
            yield word + " "
            await asyncio.sleep(0.04)
        return

    full_reply = ""
    try:
        client = ollama.AsyncClient(host=config.OLLAMA_HOST)
        stream = await client.chat(
            model=config.SAGE_MODEL,
            messages=messages,
            stream=True,
        )

        if hasattr(stream, "__aiter__"):
            async for chunk in stream:
                if isinstance(chunk, dict):
                    token = chunk.get("message", {}).get("content", "")
                else:
                    message = getattr(chunk, "message", None)
                    token = getattr(message, "content", "") if message is not None else ""
                full_reply += token
                yield token
        else:
            message = getattr(stream, "message", None)
            token = getattr(message, "content", "") if message is not None else ""
            full_reply += token
            if token:
                yield token

        # Signal clearing to the SSE wrapper
        if "CLEARED" in full_reply.upper():
            yield "\n__CLEARED__"

    except Exception as e:
        yield f"\n[Sage error: {e}]"

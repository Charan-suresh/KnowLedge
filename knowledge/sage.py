from dataclasses import dataclass
import re
from typing import List, Dict, Any
from . import config
from .agents.inference_router import chat

@dataclass
class ClearingResult:
    cleared: bool
    response: str


_ROLE_TAG_RE = re.compile(r"\*\*\[(SYSTEM|USER|ASSISTANT)\]\*\*|\[(SYSTEM|USER|ASSISTANT)\]", re.IGNORECASE)
_FORMAT_TAG_RE = re.compile(r"</?(?:explanation|question|answer|response)>", re.IGNORECASE)


def _normalize_socratic_response(reply: str) -> str:
    cleaned = _ROLE_TAG_RE.sub("", reply or "")
    cleaned = _FORMAT_TAG_RE.sub("", cleaned)
    cleaned = cleaned.replace("Assistant:", "").replace("User:", "").replace("System instructions:", "")
    cleaned = re.sub(r" {2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

    if not cleaned:
        return "Can you walk me through one concrete example of this concept?"
    if "CLEARED" in cleaned.upper():
        return "CLEARED"

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", cleaned) if s.strip()]
    question_idx = None
    for i in range(len(sentences) - 1, -1, -1):
        if sentences[i].endswith("?") and len(sentences[i]) > 8:
            question_idx = i
            break

    if question_idx is None:
        return cleaned

    explanation = " ".join(sentences[:question_idx]).strip()
    question = sentences[question_idx]
    if explanation:
        return explanation + "\n\n" + question
    return question

def _build_history_block(chat_history: List[Dict[str, str]]) -> str:
    """Format last N turns as a [PRIOR CONVERSATION] block for injection."""
    turns = []
    idx = 1
    i = 0
    while i < len(chat_history) - 1:
        msg = chat_history[i]
        next_msg = chat_history[i + 1]
        role = (msg.get("role") or "").lower()
        next_role = (next_msg.get("role") or "").lower()
        if role in {"assistant", "sage"} and next_role in {"user", "student"}:
            q = (msg.get("content") or "").strip()
            a = (next_msg.get("content") or "").strip()
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


def run_session(concept: str, debt_log: List[Dict[str, Any]], chat_history: List[Dict[str, str]]) -> ClearingResult:
    """
    Runs a single turn of Socratic dialogue using gemma-4-E4B.
    Evaluates if the student has demonstrated mastery.
    """
    # Context building from debt log
    context_str = "\n".join([f"- {entry.get('source_text', '')}" for entry in debt_log if entry.get('source_text')])
    if not context_str:
        context_str = "No specific source text available."

    history_block = _build_history_block(chat_history[-12:])
    no_repeat_instruction = (
        "\nYou have already asked the questions above. Do NOT repeat or rephrase any of them. "
        "Your next question must probe a NEW aspect.\n"
        if history_block else ""
    )

    system_prompt = f"""You are Sage, a Socratic tutor. The student is working on: '{concept}'.
Context:
{context_str}
{history_block}{no_repeat_instruction}
Each response must do two things in order:
- Acknowledge or briefly clarify what the student said (1 sentence).
- Ask exactly one focused follow-up question probing a new aspect.

Rules:
- Never repeat or rephrase a question already asked.
- Never reveal the full answer.
- If the student has clearly demonstrated genuine understanding of all key aspects, call the `verify_comprehension` tool.
- Keep the total response under 50 words."""

    messages = [{"role": "system", "content": system_prompt}] + chat_history

    tools = [{
        'type': 'function',
        'function': {
            'name': 'verify_comprehension',
            'description': 'Call this tool ONLY when you determine the student has successfully demonstrated understanding of the concept and filled their logic gap.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'reasoning': {
                        'type': 'string',
                        'description': 'Brief explanation of why the student has cleared the concept.'
                    }
                },
                'required': ['reasoning']
            }
        }
    }]

    try:
        response = chat(
            model=config.SAGE_MODEL,
            messages=messages,
            tools=tools
        )
        
        message = response.get('message', {})
        tool_calls = message.get('tool_calls', [])
        
        cleared = False
        ai_response = message.get('content', '')

        if tool_calls:
            for tool in tool_calls:
                if tool.get('function', {}).get('name') == 'verify_comprehension':
                    cleared = True
                    ai_response = "Great job! You've successfully demonstrated comprehension of this concept."
                    break

        ai_response = _normalize_socratic_response(ai_response)

        return ClearingResult(cleared=cleared, response=ai_response)
        
    except Exception as e:
        print(f"Error communicating with Ollama API: {e}")
        return ClearingResult(cleared=False, response=f"Error: {e}")

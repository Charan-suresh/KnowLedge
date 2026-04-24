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


def _normalize_socratic_response(reply: str) -> str:
    cleaned = _ROLE_TAG_RE.sub("", reply or "")
    cleaned = cleaned.replace("Assistant:", "").replace("User:", "").replace("System instructions:", "")
    cleaned = " ".join(cleaned.split())

    if not cleaned:
        return "Can you explain that in your own words, step by step?"

    if "CLEARED" in cleaned.upper():
        return "CLEARED"

    for part in re.split(r"(?<=[?.!])\s+", cleaned):
        segment = part.strip()
        if segment.endswith("?") and len(segment) > 8:
            return segment

    return "Can you explain that in your own words, step by step?"

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

    system_prompt = f"""You are the Debt Collector. Your goal is to clear comprehension debt for heavily borrowed concept: '{concept}'. 
Use the provided context to ask questions that lead the student to the answer. 
If they are wrong, point out why their logic is inconsistent based on the Context. 
Never give the answer directly.
If you determine the student has demonstrated sufficient understanding and has "cleared" the concept, you MUST call the `verify_comprehension` tool.

Context:
{context_str}
{history_block}{no_repeat_instruction}"""

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

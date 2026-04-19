import ollama
from dataclasses import dataclass
from typing import List, Dict, Any
from . import config

@dataclass
class ClearingResult:
    cleared: bool
    response: str

def run_session(concept: str, debt_log: List[Dict[str, Any]], chat_history: List[Dict[str, str]]) -> ClearingResult:
    """
    Runs a single turn of Socratic dialogue using gemma-4-E4B.
    Evaluates if the student has demonstrated mastery.
    """
    # Context building from debt log
    context_str = "\n".join([f"- {entry.get('source_text', '')}" for entry in debt_log if entry.get('source_text')])
    if not context_str:
        context_str = "No specific source text available."

    system_prompt = f"""You are the Debt Collector. Your goal is to clear comprehension debt for heavily borrowed concept: '{concept}'. 
Use the provided context to ask questions that lead the student to the answer. 
If they are wrong, point out why their logic is inconsistent based on the Context. 
Never give the answer directly.
If you determine the student has demonstrated sufficient understanding and has "cleared" the concept, you MUST call the `verify_comprehension` tool.

Context:
{context_str}
"""

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
        client = ollama.Client(host=config.OLLAMA_HOST)
        response = client.chat(
            model=config.COLLECTOR_MODEL,
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

        return ClearingResult(cleared=cleared, response=ai_response)
        
    except Exception as e:
        print(f"Error communicating with local Ollama: {e}")
        return ClearingResult(cleared=False, response=f"Error: {e}")

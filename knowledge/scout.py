from dataclasses import dataclass
from typing import List
from . import config
from .agents.inference_router import chat
import logging

logger = logging.getLogger(__name__)

@dataclass
class ConceptTag:
    concept_tag: str
    confidence_score: float

def tag_content(text: str) -> List[ConceptTag]:
    """
    Analyzes student input using gemma-4-E2B via Ollama.
    Extracts concepts using native function calling and returns them.
    """
    if not text or not text.strip():
        return []

    tools = [{
        'type': 'function',
        'function': {
            'name': 'log_comprehension_concepts',
            'description': 'Identifies and extracts academic concepts mentioned in the text that the student might be borrowing or learning. Return a list of concepts with a confidence score.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'concepts': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'concept_tag': {
                                    'type': 'string',
                                    'description': 'The name of the learning concept, e.g., "Recursion Base Case" or "For Loop"'
                                },
                                'confidence_score': {
                                    'type': 'number',
                                    'description': 'Confidence score between 0.0 and 1.0 indicating how clearly the concept is present in the text.'
                                }
                            },
                            'required': ['concept_tag', 'confidence_score']
                        }
                    }
                },
                'required': ['concepts']
            }
        }
    }]
    
    SYSTEM_PROMPT = (
        "You are 'The Sentinel', a background observer. Your task is to analyze the student's text "
        "and calmly identify any academic or technical concepts being used or discussed. "
        "Do not be punitive; treat these as 'borrowed' concepts for knowledge tracking. "
        "Use the native function calling tool to log these concepts."
    )

    try:
        response = chat(
            model=config.SCOUT_MODEL,
            messages=[
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': f"Analyze this student input:\n\n{text}"}
            ],
            tools=tools
        )
        
        message = response.get('message', {})
        tool_calls = message.get('tool_calls', [])
        
        extracted_concepts = []
        
        if tool_calls:
            for tool in tool_calls:
                function_call = tool.get('function', {})
                if function_call.get('name') == 'log_comprehension_concepts':
                    arguments = function_call.get('arguments', {})
                    concepts = arguments.get('concepts', [])
                    for concept in concepts:
                        tag = concept.get('concept_tag')
                        score = concept.get('confidence_score')
                        if tag and score is not None:
                            extracted_concepts.append(ConceptTag(concept_tag=tag, confidence_score=float(score)))
        
        return extracted_concepts

    except Exception as e:
        logger.error(f"Error connecting to Sentinel model: {e}")
        return []

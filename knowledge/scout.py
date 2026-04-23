from dataclasses import dataclass
from collections import Counter
import re
from typing import List
from . import config
from .agents.inference_router import chat
import logging

logger = logging.getLogger(__name__)

_STOPWORDS = {
    "a", "an", "and", "as", "at", "be", "been", "but", "by", "for", "from",
    "has", "have", "i", "if", "in", "into", "is", "it", "its", "me", "my",
    "of", "on", "or", "our", "so", "than", "that", "the", "their", "then",
    "there", "these", "this", "those", "to", "was", "we", "were", "with", "you",
    "your", "btw", "via", "do", "does", "did", "can", "could", "should", "would",
}

@dataclass
class ConceptTag:
    concept_tag: str
    confidence_score: float


def _title_case_concept(text: str) -> str:
    parts = [part for part in re.split(r"\s+", text.strip()) if part]
    return " ".join(part[:1].upper() + part[1:] for part in parts)


def _fallback_concepts(text: str, limit: int = 3) -> List[ConceptTag]:
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9'-]+", text.lower())
    if not tokens:
        return []

    meaningful = [token for token in tokens if token not in _STOPWORDS and len(token) > 2]
    if not meaningful:
        meaningful = tokens[:]

    spans: List[str] = []
    current: List[str] = []
    for token in meaningful:
        if token in _STOPWORDS:
            if len(current) >= 1:
                spans.append(" ".join(current))
            current = []
            continue
        current.append(token)
        if len(current) >= 3:
            spans.append(" ".join(current))
            current = []
    if current:
        spans.append(" ".join(current))

    candidates: List[str] = []
    seen = set()
    for phrase in spans:
        phrase = phrase.strip()
        if not phrase:
            continue
        for candidate in (phrase, *phrase.split()):
            normalized = candidate.strip().lower()
            if normalized and normalized not in _STOPWORDS and normalized not in seen:
                seen.add(normalized)
                candidates.append(_title_case_concept(normalized))
            if len(candidates) >= limit:
                break
        if len(candidates) >= limit:
            break

    if not candidates:
        counts = Counter(token for token in meaningful if token not in _STOPWORDS)
        candidates = [_title_case_concept(token) for token, _ in counts.most_common(limit)]

    return [ConceptTag(concept_tag=candidate, confidence_score=0.35) for candidate in candidates[:limit]]


def _extract_concepts_from_response(response: dict, text: str) -> List[ConceptTag]:
    message = response.get("message", {}) or {}
    extracted_concepts: List[ConceptTag] = []

    tool_calls = message.get("tool_calls", []) or []
    if tool_calls:
        for tool in tool_calls:
            function_call = tool.get("function", {})
            if function_call.get("name") != "log_comprehension_concepts":
                continue

            arguments = function_call.get("arguments", {}) or {}
            if isinstance(arguments, str):
                try:
                    import json

                    arguments = json.loads(arguments)
                except Exception:
                    arguments = {}
            concepts = arguments.get("concepts", []) or []
            for concept in concepts:
                tag = concept.get("concept_tag")
                score = concept.get("confidence_score")
                if tag and score is not None:
                    extracted_concepts.append(
                        ConceptTag(concept_tag=str(tag).strip(), confidence_score=float(score))
                    )

    if extracted_concepts:
        return extracted_concepts

    content = str(message.get("content", "") or "").strip()
    if content:
        try:
            payload = re.search(r"\{.*\}", content, flags=re.DOTALL)
            if payload:
                import json

                parsed = json.loads(payload.group(0))
                concepts = parsed.get("concepts", []) if isinstance(parsed, dict) else []
                for concept in concepts:
                    tag = concept.get("concept_tag")
                    score = concept.get("confidence_score")
                    if tag and score is not None:
                        extracted_concepts.append(
                            ConceptTag(concept_tag=str(tag).strip(), confidence_score=float(score))
                        )
        except Exception:
            extracted_concepts = []

    if extracted_concepts:
        cleaned: List[ConceptTag] = []
        seen = set()
        for item in extracted_concepts:
            tag = (item.concept_tag or "").strip()
            if not tag:
                continue
            key = tag.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(ConceptTag(concept_tag=tag, confidence_score=max(0.0, min(1.0, float(item.confidence_score)))))
        if cleaned:
            return cleaned

    return _fallback_concepts(text)

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

        return _extract_concepts_from_response(response, text)

    except Exception as e:
        logger.error(f"Error connecting to Sentinel model: {e}")
        return _fallback_concepts(text)

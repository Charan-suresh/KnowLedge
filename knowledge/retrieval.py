import sys
import logging
from typing import Optional, Dict, Any, List
import httpx

from .rag import query_context, get_collection as init_vectorstore
from . import config
from .agents.ollama_client import chat

logger = logging.getLogger(__name__)

def verify_offline(model: str = "gemma4:e4b") -> bool:
    """
    Checks if Ollama is reachable locally and if the specified model is available.
    Returns True if offline inference is ready, False otherwise.
    """
    try:
        headers = {"Authorization": f"Bearer {config.OLLAMA_AUTH_TOKEN}"} if config.OLLAMA_AUTH_TOKEN else {}
        response = httpx.get(f"{config.OLLAMA_BASE_URL}/api/tags", timeout=3, headers=headers)
        response.raise_for_status()
        models = [m["name"] for m in response.json().get("models", [])]
        if any(model == m or m.startswith(model + ":") for m in models):
            print(f"✅ Offline verification passed: Ollama is running and '{model}' is available.")
            return True
        else:
            print(f"❌ Offline verification failed: Model '{model}' not found in local Ollama.")
            return False
    except httpx.HTTPError as e:
        print(f"❌ Offline verification failed: Could not connect to Ollama at {config.OLLAMA_BASE_URL}.")
        print(f"Details: {e}")
        return False

def build_context(question: str, source_filter: Optional[str] = None) -> str:
    """
    Retrieves relevant chunks from ChromaDB and filters out weak matches (distance > 0.5).
    Joins the remaining chunks into a single formatted context string ready for injection.
    """
    try:
        results = query_context(question, n_results=5)
    except Exception as e:
        print(f"Warning: Failed to retrieve context: {e}")
        return ""
        
    if not results:
        return ""
        
    valid_chunks = []
    
    for res in results:
        if res.get('distance', 1.0) <= 0.5:
            # Enforce source filter if a source filter is provided
            if source_filter and res.get('metadata', {}).get('source') != source_filter:
                continue
                
            doc = res.get('document', '')
            if doc:
                valid_chunks.append(doc)
                
    if not valid_chunks:
        return ""
        
    return "\\n\\n---\\n\\n".join(valid_chunks)

def rag_query(question: str, source_filter: Optional[str] = None, model: str = "gemma4:e4b") -> Dict[str, Any]:
    """
    Executes an end-to-end offline RAG pipeline natively using Ollama.
    Retrieves formatted context via build_context(), fetches the raw dicts,
    and formats a strict prompt for Gemma 4 to answer.
    
    Returns a dict with:
    - "answer": the model's text response
    - "context_used": list of chunk dictionaries used
    - "model": name of the inference model
    - "had_context": boolean indicating if context was found
    """
    # 1. Build string context
    context_str = build_context(question, source_filter=source_filter)
    
    had_context = bool(context_str.strip())
    context_used = []
    
    # Optional performance optimization: since build_context consumed the query once, 
    # we explicitly fetch it here to populate context_used list formatting rule.
    # Because local Chromedb query takes <10ms, avoiding heavy refactoring of build_context 
    # to return a tuple instead of a string keeps it to the requested signature.
    if had_context:
        try:
            raw_results = query_context(question, n_results=5)
            for res in raw_results:
                if res.get('distance', 1.0) <= 0.5:
                    if source_filter and res.get('metadata', {}).get('source') != source_filter:
                        continue
                    context_used.append(res)
        except Exception as e:
            logger.warning("Unable to hydrate context_used from vector store: %s", e)

    # 3. Construct strict system prompt
    system_prompt = (
        "You are an expert technical assistant answering questions based strictly on the provided context. "
        "If the context does not contain the information required to answer the question, "
        "you must explicitly state that the context does not cover the question and decline to answer based on external knowledge."
    )
    
    if had_context:
        user_prompt = f"Context:\\n{context_str}\\n\\nQuestion:\\n{question}"
    else:
        user_prompt = f"Context:\\nNo context retrieved from the database.\\n\\nQuestion:\\n{question}"

    # 4. Generate Response via Ollama
    try:
        response = chat(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        answer = response.get("message", {}).get("content", "")
    except Exception as e:
        answer = f"Error during local Ollama inference: {str(e)}"

    return {
        "answer": answer,
        "context_used": context_used,
        "model": model,
        "had_context": had_context
    }

def get_relevant_context(concept_tag: str) -> str:
    """
    Retrieves the most relevant educational snippets from ChromaDB 
    to ground the AI's questions.
    """
    return build_context(concept_tag)


import os
import logging
from typing import List, Dict, Any, Optional
from . import config

try:
    import chromadb
    from chromadb.utils import embedding_functions
except ImportError:
    chromadb = None
    embedding_functions = None
    print("chromadb not available — RAG disabled")

try:
    import pdfplumber
except ImportError:
    pdfplumber = None
    print("pdfplumber not available — PDF ingestion disabled")


_collection = None
_vectorstore_disabled = False
_vectorstore_disable_reason = ""
logger = logging.getLogger(__name__)


def _disable_vectorstore(reason: str) -> None:
    global _vectorstore_disabled, _vectorstore_disable_reason
    if not _vectorstore_disabled:
        _vectorstore_disabled = True
        _vectorstore_disable_reason = reason
        logger.warning("Disabling Chroma RAG: %s", reason)


def _ollama_embeddings_expected() -> bool:
    return config.OLLAMA_BASE_URL != config.DEFAULT_OLLAMA_BASE_URL or config.INFERENCE_BACKEND == "ollama"


def init_vectorstore() -> Optional["chromadb.Collection"]:
    global _collection, _vectorstore_disabled
    if _collection is not None:
        return _collection
    if _vectorstore_disabled:
        return None
    if chromadb is None or embedding_functions is None:
        _disable_vectorstore("chromadb not installed")
        return None

    if not _ollama_embeddings_expected():
        _disable_vectorstore(
            f"Ollama embeddings are not configured for backend '{config.INFERENCE_BACKEND}'."
        )
        return None

    try:
        client = chromadb.PersistentClient(path=config.CHROMA_PATH)
        
        ef = embedding_functions.OllamaEmbeddingFunction(
            url=f"{config.OLLAMA_BASE_URL}/api/embeddings",
            model_name="nomic-embed-text"
        )
        
        _collection = client.get_or_create_collection(
            name="course_material",
            embedding_function=ef
        )
        return _collection
    except Exception as e:
        _disable_vectorstore(str(e))
        return None

# Backward compatibility alias
def get_collection() -> Optional[chromadb.Collection]:
    return init_vectorstore()

def extract_text_from_file(file_path: str) -> str:
    """
    Reads all pages of a PDF or plain text and extracts text.
    Handles empty files gracefully.
    """
    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' not found.")
        return ""
        
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == ".txt":
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            print(f"Error reading TXT {file_path}: {e}")
            return ""
            
    elif ext == ".pdf":
        if pdfplumber is None:
            print("pdfplumber not installed — cannot read PDF")
            return ""
        text_pieces = []
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_pieces.append(page_text)
            return "\\n\\n".join(text_pieces)
        except Exception as e:
            print(f"Error reading PDF {file_path}: {e}")
            return ""
    else:
        print(f"Unsupported file extension: {ext}")
        return ""


def chunk_text(text: str) -> List[str]:
    """
    Splits text into chunks by paragraphs, targeting 800-1200 characters per chunk.
    Avoids very small chunks (< 80 chars) by merging them.
    Each chunk is designed to represent roughly ONE concept.
    """
    paragraphs = [p.strip() for p in text.split('\\n\\n') if p.strip()]
    chunks = []
    current_chunk = ""

    for para in paragraphs:
        # Estimate size if we append this paragraph
        proposed_len = len(current_chunk) + len(para) + (2 if current_chunk else 0)
        
        # If adding the paragraph exceeds upper limit and we have enough chars
        if proposed_len > 1200 and len(current_chunk) >= 80:
            chunks.append(current_chunk)
            current_chunk = para
        else:
            if current_chunk:
                current_chunk += "\\n\\n" + para
            else:
                current_chunk = para

    # Handle the final chunk
    if len(current_chunk) >= 80:
        chunks.append(current_chunk)
    elif current_chunk and chunks:
        # Merge tiny leftover into the last chunk
        chunks[-1] += "\\n\\n" + current_chunk
    elif current_chunk:
        # If it's the only one and it's tiny
        chunks.append(current_chunk)

    return chunks


def ingest_file(file_path: str, source_label: str) -> int:
    """
    Extracts text from a file, chunks it based on concept rules, 
    and ingests it into ChromaDB with embeddings and metadata.
    Returns the number of chunks successfully ingested.
    """
    print(f"Starting ingestion for {file_path}...")
    text = extract_text_from_file(file_path)
    if not text:
        print(f"Warning: No valid text extracted from {file_path}. Skipping.")
        return 0

    chunks = chunk_text(text)
    if not chunks:
        print(f"Warning: No valid chunks generated from {file_path}. Skipping.")
        return 0

    import uuid
    # Use random UUID or specific IDs. Specific chunks allow easy updates
    _base_id = uuid.uuid4().hex[:6]
    ids = [f"{source_label}_{_base_id}_chunk_{i}" for i in range(len(chunks))]
    metadatas = [{"source": source_label, "chunk_index": i} for i in range(len(chunks))]

    collection = init_vectorstore()
    if collection is None:
        return 0
    
    try:
        collection.add(
            documents=chunks,
            metadatas=metadatas,
            ids=ids
        )
        return len(chunks)
    except Exception as e:
        _disable_vectorstore(str(e))
        return 0

# For backward compatibility
def ingest_pdf(file_path: str, source_name: str) -> int:
    return ingest_file(file_path, source_name)

def list_sources() -> List[str]:
    """
    Returns a list of unique source labels currently in the vector store.
    """
    try:
        collection = init_vectorstore()
        if collection is None:
            return []
        results = collection.get(include=["metadatas"])
        metas = results.get("metadatas", [])
        if not metas:
            return []
        sources = set()
        for m in metas:
            src = m.get("source")
            if src:
                sources.add(src)
        return list(sources)
    except Exception as e:
        print(f"Error listing sources: {e}")
        return []

def delete_source(source_label: str):
    """
    Deletes all vectors associated with a specific source.
    """
    try:
        collection = init_vectorstore()
        if collection is None:
            return
        collection.delete(where={"source": source_label})
        print(f"Deleted source: {source_label}")
    except Exception as e:
        print(f"Error deleting source {source_label}: {e}")

def query_context(query: str, n_results: int = 3) -> List[Dict[str, Any]]:
    """
    Queries ChromaDB to find the most relevant chunks for a given query.
    Returns a structured list containing documents/texts, metadata, and distances.
    """
    collection = init_vectorstore()
    if collection is None:
        return []
    formatted_results = []
    
    try:
        results = collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        if not results or not results.get("documents") or not results["documents"][0]:
            return []
            
        docs = results["documents"][0]
        metas = results["metadatas"][0]
        dists = results["distances"][0] if results.get("distances") else [0.0] * len(docs)
        
        for doc, meta, dist in zip(docs, metas, dists):
            formatted_results.append({
                "document": doc,   # Maintained for retrieval.py
                "text": doc,       # Added for user's explicit manual test case check
                "metadata": meta,
                "distance": dist
            })
            
    except Exception as e:
        _disable_vectorstore(str(e))
        
    return formatted_results

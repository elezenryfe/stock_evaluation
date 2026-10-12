import logging
import uuid
from typing import Optional

logger = logging.getLogger(__name__)

_chroma_client: Optional[object] = None
_chroma_available = False

COLLECTION_PREFIX = "stock_guidance"
TOP_K = 8


def _get_client():
    global _chroma_client, _chroma_available
    if _chroma_client is not None:
        return _chroma_client
    try:
        import chromadb
        _chroma_client = chromadb.PersistentClient(path="./chroma_data")
        _chroma_available = True
        logger.info("ChromaDB client initialized")
    except Exception as e:
        logger.warning(f"Could not initialize ChromaDB: {e}. Using in-memory fallback.")
        _chroma_client = None
        _chroma_available = False
    return _chroma_client


def get_collection_name(ticker: str) -> str:
    return f"{COLLECTION_PREFIX}_{ticker.lower()}"


def index_documents(
    ticker: str,
    chunks: list[dict],
    metadata: dict,
) -> list[str]:
    client = _get_client()
    if client is None:
        return []

    collection_name = get_collection_name(ticker)
    try:
        collection = client.get_or_create_collection(name=collection_name)
    except Exception:
        collection = client.create_collection(name=collection_name)

    ids = [str(uuid.uuid4()) for _ in chunks]
    texts = [c["text"] for c in chunks]
    metadatas = [
        _sanitize_metadata({**metadata, "is_management": c.get("is_management", False)})
        for c in chunks
    ]

    try:
        collection.add(ids=ids, documents=texts, metadatas=metadatas)
        logger.info(f"Indexed {len(chunks)} chunks in {collection_name}")
    except Exception as e:
        logger.warning(f"ChromaDB add failed: {e}")
        return []

    return ids


def _sanitize_metadata(meta: dict) -> dict:
    sanitized = {}
    for key, value in meta.items():
        if value is None:
            sanitized[key] = ""
        elif isinstance(value, (str, int, float, bool)):
            sanitized[key] = value
        else:
            sanitized[key] = str(value)
    return sanitized


def retrieve_relevant_chunks(
    ticker: str,
    query: str,
    top_k: int = TOP_K,
) -> list[dict]:
    client = _get_client()
    if client is None:
        return []

    collection_name = get_collection_name(ticker)
    try:
        collection = client.get_collection(name=collection_name)
    except Exception:
        return []

    results = collection.query(query_texts=[query], n_results=top_k)
    chunks = []
    if results["documents"] and results["documents"][0]:
        for i, doc in enumerate(results["documents"][0]):
            distance = results.get("distances", [[0.0]])[0][i] if results.get("distances") else 0.0
            metadata = results.get("metadatas", [[{}]])[0][i] if results.get("metadatas") else {}
            chunks.append({
                "text": doc,
                "score": float(1.0 - distance) if distance else 1.0,
                "is_management": metadata.get("is_management", False),
            })
    return chunks

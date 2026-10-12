import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

_embedding_model: Optional[object] = None
_model_available = False


def _load_model():
    global _embedding_model, _model_available
    if _embedding_model is not None:
        return
    try:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        _model_available = True
        logger.info(f"Loaded embedding model: {EMBEDDING_MODEL_NAME}")
    except Exception as e:
        logger.warning(f"Could not load embedding model: {e}. Using fallback.")
        _model_available = False


def embed_texts(texts: list[str]) -> np.ndarray:
    _load_model()
    if not _model_available or _embedding_model is None:
        return np.zeros((len(texts), EMBEDDING_DIM), dtype=np.float32)
    return _embedding_model.encode(texts, show_progress_bar=False)


def embed_query(query: str) -> list[float]:
    _load_model()
    if not _model_available or _embedding_model is None:
        return [0.0] * EMBEDDING_DIM
    result = _embedding_model.encode([query], show_progress_bar=False)
    return result[0].tolist()

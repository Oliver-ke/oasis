from functools import lru_cache

from langchain_huggingface import HuggingFaceEmbeddings

_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def get_embedder() -> HuggingFaceEmbeddings:
    """Shared local embedder for BOTH Chroma and Neo4j entry-point search."""
    return HuggingFaceEmbeddings(model_name=_MODEL)

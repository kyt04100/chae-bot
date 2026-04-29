"""Cached lazy loader for embedding models so ingest and retrieve share one instance."""
from __future__ import annotations

from functools import lru_cache

EMBED_MODEL_NAME = "BAAI/bge-small-en-v1.5"  # 384-dim, ~130MB, CPU-friendly
EMBED_DIM = 384


@lru_cache(maxsize=1)
def embedder():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(EMBED_MODEL_NAME)


def encode(texts: list[str]) -> list[list[float]]:
    model = embedder()
    arr = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return arr.tolist()

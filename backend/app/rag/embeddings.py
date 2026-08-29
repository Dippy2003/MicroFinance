"""
Embedding model for RAG.

We use sentence-transformers all-MiniLM-L6-v2: a small (~80MB) model that runs
locally on CPU and produces 384-dimensional vectors. Chosen because it is free,
offline (no API, no rate limit, demo cannot fail on a network blip), and the
LLM layer already uses Groq separately.

VERIFIED: Groq does NOT serve any embedding model (checked against the live API),
so embeddings must be local. The model is loaded lazily and cached so the ~80MB
load happens once per process, not per call. EMBED_DIM must match the pgvector
column dimension in scripts/schema.sql.
"""

from __future__ import annotations

from functools import lru_cache

EMBED_MODEL_NAME = "all-MiniLM-L6-v2"
EMBED_DIM = 384  # must equal vector(N) in schema.sql


@lru_cache(maxsize=1)
def _model():
    """Load the model once. Imported lazily so importing this module is cheap."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBED_MODEL_NAME)


def embed(text: str) -> list[float]:
    """Embed a single string into a 384-dim list of floats."""
    vec = _model().encode(text, normalize_embeddings=True)
    return vec.tolist()


def embed_many(texts: list[str]) -> list[list[float]]:
    """Embed many strings at once (faster than one-by-one for ingestion)."""
    vecs = _model().encode(texts, normalize_embeddings=True)
    return [v.tolist() for v in vecs]

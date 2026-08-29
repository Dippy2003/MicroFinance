"""
RAG retriever.

FROZEN contract (unchanged since Stage 1):
    retrieve(query: str, segment: str, k: int = 5) -> list[Chunk]
    Chunk = {text: str, source: str}

STAGE 6 - real semantic retrieval:
`retrieve()` now embeds the query with local MiniLM and runs a cosine-similarity
search over Supabase pgvector (via the match_rag_chunks RPC from schema.sql).

GRACEFUL FALLBACK:
If Supabase is not configured, or the call/embedding fails, we fall back to a
local keyword-overlap search over the SAME knowledge (app/rag/knowledge.py). So
the whole pipeline still runs end to end with zero external setup, and a network
or DB hiccup at demo time degrades retrieval instead of crashing it. The return
shape is identical either way, so nothing upstream knows or cares which path ran.
"""

from __future__ import annotations

from app import config
from app.models import Chunk
from app.rag.knowledge import KNOWLEDGE


def _keyword_fallback(query: str, segment: str, k: int) -> list[Chunk]:
    """Local keyword-overlap search over the in-memory knowledge base.

    Ranks the segment's chunks by word overlap with the query and returns the
    top k. Used when Supabase is unavailable. Not semantic, but deterministic
    and dependency-free.
    """
    docs = KNOWLEDGE.get(segment, [])
    if not docs:
        return []

    query_words = {w.lower() for w in query.split() if w}

    def overlap(chunk: Chunk) -> int:
        chunk_words = {w.lower().strip(".,()") for w in chunk.text.split()}
        return len(query_words & chunk_words)

    ranked = sorted(docs, key=overlap, reverse=True)
    return ranked[:k]


def _pgvector_search(query: str, segment: str, k: int) -> list[Chunk]:
    """Semantic search over Supabase pgvector. Raises on any failure so the
    caller can fall back."""
    from supabase import create_client

    from app.rag.embeddings import embed

    client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
    query_embedding = embed(query)

    # Calls the SQL function defined in scripts/schema.sql.
    response = client.rpc(
        "match_rag_chunks",
        {
            "query_embedding": query_embedding,
            "match_segment": segment,
            "match_count": k,
        },
    ).execute()

    rows = response.data or []
    return [Chunk(text=row["text"], source=row["source"]) for row in rows]


def retrieve(query: str, segment: str, k: int = 5) -> list[Chunk]:
    """Return up to k chunks relevant to `query` for the given `segment`.

    Tries Supabase pgvector (semantic) first; falls back to local keyword search
    on any problem. Unknown segments return an empty list, which the
    orchestrator treats as 'no providers found'.
    """
    if config.SUPABASE_URL and config.SUPABASE_KEY:
        try:
            results = _pgvector_search(query, segment, k)
            if results:
                return results
            # Empty result: fall through to keyword fallback rather than return
            # nothing, in case the table was never ingested.
        except Exception:
            # Any error (network, missing table/RPC, bad key) -> degrade locally.
            pass

    return _keyword_fallback(query, segment, k)

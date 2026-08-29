"""
Ingestion script: embed the knowledge base into Supabase pgvector.

Run once (after applying scripts/schema.sql in the Supabase SQL editor):

    cd backend
    python -m scripts.ingest

What it does:
  1. Loads every (segment, chunk) from app/rag/knowledge.py.
  2. Embeds each chunk's text with local MiniLM (384-dim).
  3. Deletes existing rag_chunks rows and inserts the fresh set, so re-running
     is idempotent (no duplicates).

Requires SUPABASE_URL and SUPABASE_KEY in backend/.env. Use the service-role key
for ingestion (it bypasses row-level security for the insert/delete).
"""

from __future__ import annotations

import sys

from app import config
from app.rag.embeddings import EMBED_DIM, embed_many
from app.rag.knowledge import all_chunks


def main() -> None:
    if not config.SUPABASE_URL or not config.SUPABASE_KEY:
        print("ERROR: SUPABASE_URL / SUPABASE_KEY not set in backend/.env")
        sys.exit(1)

    from supabase import create_client

    client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

    pairs = all_chunks()
    print(f"Loaded {len(pairs)} chunk(s) from the knowledge base.")

    # Embed all texts in one batch (faster, single model load).
    texts = [chunk.text for _, chunk in pairs]
    print(f"Embedding with MiniLM ({EMBED_DIM}-dim)... (first run downloads ~80MB)")
    vectors = embed_many(texts)

    rows = [
        {
            "segment": segment,
            "text": chunk.text,
            "source": chunk.source,
            "embedding": vector,
        }
        for (segment, chunk), vector in zip(pairs, vectors)
    ]

    # Idempotent: clear the table, then insert the fresh set.
    # The .neq filter is a delete-all that satisfies Supabase's require-filter rule.
    print("Clearing existing rag_chunks rows...")
    client.table("rag_chunks").delete().neq("id", 0).execute()

    print(f"Inserting {len(rows)} row(s)...")
    client.table("rag_chunks").insert(rows).execute()

    print("Ingestion complete.")


if __name__ == "__main__":
    main()

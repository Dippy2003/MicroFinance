-- pgvector schema for the MicroLoan RAG store.
-- Run this once in the Supabase SQL editor before ingesting.
--
-- Vector dimension is 384 to match all-MiniLM-L6-v2 (app/rag/embeddings.py).
-- If you change the embedding model, change vector(384) AND EMBED_DIM together.

-- 1) Enable the pgvector extension (Supabase ships it; this is idempotent).
create extension if not exists vector;

-- 2) The chunks table: one row per knowledge chunk, keyed by segment.
create table if not exists rag_chunks (
    id          bigint generated always as identity primary key,
    segment     text        not null,         -- 'informal_vendor' | 'micro_business'
    text        text        not null,         -- the chunk content
    source      text        not null,         -- citation, returned to the app
    embedding   vector(384) not null,         -- MiniLM embedding of `text`
    created_at  timestamptz not null default now()
);

-- 3) Index for fast approximate nearest-neighbour search by cosine distance.
--    ivfflat needs data present to build well; for our tiny corpus it is fine
--    either way, but we create it for correctness and to mirror production.
create index if not exists rag_chunks_embedding_idx
    on rag_chunks
    using ivfflat (embedding vector_cosine_ops)
    with (lists = 1);

-- 4) Helper index so per-segment filtering is cheap.
create index if not exists rag_chunks_segment_idx on rag_chunks (segment);

-- 5) Similarity search function the app calls via Supabase RPC.
--    Filters by segment, orders by cosine distance (<=>), returns top k.
--    SECURITY: returns only text + source (never the raw embedding).
create or replace function match_rag_chunks(
    query_embedding vector(384),
    match_segment   text,
    match_count     int default 5
)
returns table (text text, source text, similarity float)
language sql stable
as $$
    select
        c.text,
        c.source,
        1 - (c.embedding <=> query_embedding) as similarity
    from rag_chunks c
    where c.segment = match_segment
    order by c.embedding <=> query_embedding
    limit match_count;
$$;

# Developer Handoff

MicroLoan AI Agent (AgenTrix 2026). This doc gets a new backend or frontend dev
running and explains where things stand. For architecture and the frozen
contracts, read `README.md` first.

Status: Stages 1-7 complete and pushed (`main`, last commit "Stage 7: Next.js 15
frontend + live SSE trace"). Stage 8 (hardening + demo polish) is not started.

You will be given `backend/.env` and `frontend/.env.local` separately (they are
gitignored, NOT in the repo). Drop them in after cloning. The Groq key in that
`.env` is a SHARED free-tier key, so if several of us hammer it at once you may
hit rate limits; that shows up as agents using their fallback, not a crash.
The Supabase project referenced there is already set up and ingested, so you do
NOT need to run the schema or ingestion unless you are pointing at a new project.

---

## TL;DR run it locally

Two processes. Open two terminals.

**1. Backend (FastAPI, port 8000)**

```bash
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1          # Windows PowerShell
# (Mac/Linux: source .venv/bin/activate)
pip install -r requirements.txt
# Drop in the backend/.env you were given (do NOT commit it).
# If starting from scratch instead: copy .env.example .env  (Mac/Linux: cp)
uvicorn app.main:app --reload
```

Check: open http://localhost:8000/health -> `{"status":"ok",...}`

**2. Frontend (Next.js 15, port 3000)**

```bash
cd frontend
npm install
# Drop in the frontend/.env.local you were given.
# If starting from scratch: copy .env.local.example .env.local  (Mac/Linux: cp)
npm run dev
```

Open http://localhost:3000, fill the form (a default vendor profile is
pre-filled), click "Get loan advice", and watch the live trace stream.

You need BOTH running. The frontend calls the backend; the backend talks to Groq
(and optionally Supabase).

### Success looks like

With the default pre-filled vendor profile, clicking "Get loan advice" should:

- stream ~20-25 trace lines into the live panel (Planner -> SegmentRouter ->
  EligibilityGate -> ProviderMatcher -> DocPreparer + DebtAdvisor -> Evaluator),
- end with a green DONE verdict,
- show ~3 ranked provider cards with LOLC Finance recommended (highlighted),
- show a document checklist and a debt-advice paragraph.

If you instead see every agent line say "using fallback", the Groq key is
missing or rate-limited (the app still runs, just without LLM output).

---

## Secrets (backend/.env)

`backend/.env` is gitignored. Required and optional keys (template in
`backend/.env.example`):

- `GROQ_API_KEY` (REQUIRED) - free key from https://console.groq.com . Without
  it, every agent falls back to its deterministic rule, so the app still runs
  but the output is not LLM-generated.
- `GROQ_MODEL` - `openai/gpt-oss-120b` (free tier).
- `GROQ_MODEL_FAST` - defaults to `llama-3.3-70b-versatile`.
- `SUPABASE_URL`, `SUPABASE_KEY` (OPTIONAL) - for real pgvector RAG. Use the
  `service_role` key. If unset, `retrieve()` falls back to local keyword search
  over the same knowledge, so the app still works end to end.
- `AGENT_REQUEST_LIMIT` (default 3), `MAX_EVALUATOR_LOOPS` (default 2),
  `RAG_DEFAULT_K` (default 5).

Frontend env (`frontend/.env.local`): just `NEXT_PUBLIC_API_BASE`
(default `http://localhost:8000`).

---

## RAG store setup (only if using Supabase)

One-time, in the Supabase SQL editor:

1. Run `backend/scripts/schema.sql` (creates `rag_chunks`, indexes, and the
   `match_rag_chunks` RPC; vector dimension is 384).
2. Ingest the knowledge base: `cd backend && python -m scripts.ingest`
   (first run downloads the ~80MB MiniLM model).

Embeddings are LOCAL (`sentence-transformers all-MiniLM-L6-v2`, 384-dim).
Groq does NOT serve an embeddings model (verified against the live API), so do
not try to embed via Groq.

---

## How the system fits together

```
BorrowerProfile
  -> Segment Router        (classify: informal_vendor | micro_business | ...)
  -> Eligibility Gate      (conditional: stop here if not eligible)
  -> Provider Matcher      (RAG retrieve + rank + compare)
  -> Doc Preparer + Debt Advisor   (run in parallel)
  -> Evaluator             (done / loop / escalate; LOOP re-ranks on income change)
```

Explicit orchestration: a Planner outputs a structured `Plan` (data), and the
Runner executes it (serial stages, parallel steps via `asyncio.gather`, the
conditional gate enforced in code). The LLM proposes; our code disposes.

### Backend layout (`backend/app/`)

- `models.py` - FROZEN Pydantic contracts. Do NOT change shapes without a
  decision; agents, API, and frontend all depend on them.
- `config.py` - all tunables (model, limits) in one place.
- `trace.py` - `Tracer`, an append-only `list[str]`; optional `on_append`
  callback feeds the live SSE stream.
- `main.py` - FastAPI. `POST /advise` (structured result),
  `GET /advise/stream?profile=<json>` (live SSE trace + final result frame).
- `rag/` - `knowledge.py` (the sourced chunks), `embeddings.py` (MiniLM),
  `retriever.py` (`retrieve(query, segment, k)`; pgvector with keyword fallback).
- `agents/` - one module per agent. Each builds a PydanticAI `Agent`, has a
  typed `output_type`, a real prompt, and a deterministic fallback on failure.
  `llm.py` builds the Groq model + `UsageLimits`; `base.py` runs an agent.
- `orchestrator/` - `plan.py`, `planner.py`, `steps.py` (maps step -> agent),
  `evaluator.py`, `runner.py` (`run_pipeline`).
- `cli.py` - run the pipeline in the terminal (see below).
- `scripts/` - `schema.sql`, `ingest.py`.

### Frontend layout (`frontend/`)

- `app/page.tsx` - single client page: form -> opens SSE -> renders live trace,
  verdict, ranked match cards, document checklist, debt advice, and the
  income-change re-query control.
- `app/components/` - `TracePanel.tsx`, `MatchCard.tsx`.
- `lib/types.ts` - TS mirrors of the frozen backend contracts (keep in sync by
  hand if a backend model changes).
- `lib/api.ts` - `streamAdvice()` opens the `EventSource` and dispatches frames.

---

## Frozen contracts (do not change without a decision)

- RAG: `retrieve(query: str, segment: str, k: int = 5) -> list[Chunk]`,
  `Chunk = {text, source}`
- Trace: append-only `list[str]`, rendered verbatim by the frontend
- API: `POST /advise {profile} -> {verdict, matches, trace}`;
  `GET /advise/stream` -> SSE of trace lines
- Models: `BorrowerProfile, SegmentDecision, EligibilityResult, ProviderMatch,
  Verdict`

Note: the document checklist and debt advice are NOT separate response fields;
they flow through the `trace` and the frontend extracts them. `income_change_to`
is an optional query param (not in the request body), so the body contract holds.

---

## Quick verification commands (backend)

There is NO formal test suite (no pytest). These CLI commands are the smoke
tests; they call the same `run_pipeline` the API uses. From `backend/` with the
venv active:

```bash
python -m app.cli                      # Segment A vendor, expect DONE
python -m app.cli --business           # Segment B SME, expect DONE
python -m app.cli --ineligible         # expect ESCALATE
python -m app.cli --income-change-to 200000   # re-query loop: DONE -> LOOP -> DONE
python -m app.check_router             # asserts A->vendor, B->business
```

These call the same `run_pipeline` the API uses.

---

## Gotchas

- Run BOTH servers; the page is blank-ish without the backend.
- Windows console + Groq Unicode: the CLI forces UTF-8 output. If you add new
  print paths, keep that in mind.
- `uvicorn --reload` picks up backend edits. Without `--reload`, restart after
  changes (a running server keeps the old code).
- House style: NO em dashes anywhere (code, comments, trace strings, docs).
- Commits: author as yourself, no Claude co-author trailer, one commit per
  logical chunk. Do not commit `.env`, `node_modules/`, `.next/`, or
  `backend/uvicorn.log` (all gitignored; `uvicorn.log` is a stray local log,
  safe to delete).

---

## What is left (Stage 8: hardening + demo polish, NOT started)

- Failure-case UX: clearer escalate and error states, loading indicators,
  disable controls mid-run, handle a dropped SSE connection gracefully.
- Backend robustness: friendly error if `GROQ_API_KEY` is missing; surface
  partial results if one agent fails.
- A real browser click-through of every interaction (the SSE path is verified
  over HTTP, but not yet manually clicked end to end in a browser).
- Optional: a couple of preset demo profiles in the UI for fast switching.

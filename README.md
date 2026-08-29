# MicroLoan AI Agent (AgenTrix 2026)

A general-purpose AI loan-advisory agent for underbanked Sri Lanka. The
architecture routes ANY borrower segment to segment-specific logic; for the demo
we build two segments deep:

- **A - Informal vendor** -> microfinance providers
- **B - Micro / small business** -> bank & finance-company loans

**Principle: general in architecture, narrow in demo.**

## Architecture (explicit orchestration, not native tool-calling)

```
BorrowerProfile -> Segment Router -> [conditional] Eligibility Gate
   -> Provider Matcher (parallel retrieval, ranked)
   -> Doc Preparer + Debt Advisor
   -> Evaluator (re-query loop on income change)
```

A **planner** agent outputs a structured plan; our application code executes it
(`asyncio.gather` for parallel runs); an **evaluator** agent decides
done / loop / escalate. Every decision is appended to a human-readable `trace`
the frontend renders live.

## Stack
- Agents: Python + **PydanticAI**, LLM via **Groq** free tier
  (`openai/gpt-oss-120b`)
- Backend: **FastAPI** (+ SSE endpoint for the live trace)
- RAG: **Supabase pgvector**
- Frontend: **Next.js 15** (App Router)

## Frozen contracts
- RAG: `retrieve(query, segment, k=5) -> list[Chunk]`, `Chunk = {text, source}`
- Trace: append-only `list[str]`, rendered verbatim
- API: `POST /advise {profile} -> {verdict, matches, trace}`;
  `GET /advise/stream` -> SSE of trace lines
- Models: `BorrowerProfile, SegmentDecision, EligibilityResult, ProviderMatch,
  Verdict`

## Run the backend (Stage 1)

```bash
cd backend
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env   # add your GROQ_API_KEY (not needed for Stage 1 stub)
uvicorn app.main:app --reload
```

Then:
- `GET  http://localhost:8000/health`
- `POST http://localhost:8000/advise`  (JSON BorrowerProfile body)
- `GET  http://localhost:8000/advise/stream?profile=<json>`  (SSE live trace)

### Set up the RAG store (Stage 6, one time)

1. In the Supabase SQL editor, run `backend/scripts/schema.sql`.
2. Put `SUPABASE_URL` and the `service_role` key in `backend/.env`.
3. Ingest the knowledge base: `python -m scripts.ingest`.

If Supabase is not configured, `retrieve()` falls back to local keyword search,
so the app still runs end to end.

## Run the frontend (Stage 7)

```bash
cd frontend
npm install
cp .env.local.example .env.local   # points at http://localhost:8000
npm run dev                         # http://localhost:3000
```

The page has a borrower-profile form, a live SSE trace panel, ranked provider
match cards, a document checklist, debt advice, and an income-change re-query
control that triggers the re-rank loop.

## Build stages

1. Structure + models + FastAPI skeleton + stub retriever
2. Orchestrator spine: planner + execution loop + trace (Segment A)
3. The 5 agents with real prompts (Segment A)
4. Add Segment B + provider comparison/ranking
5. Re-query loop (income change -> re-plan -> re-rank)
6. Real RAG: pgvector schema + ingestion + real `retrieve()`
7. Next.js 15 frontend  <- current
8. Hardening + demo polish

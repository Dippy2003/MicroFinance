"""
Central configuration.

Everything tunable lives here so it can be changed in ONE place and explained
in one breath during judging: which model, which provider, and the usage limit
that protects the free-tier quota.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()  # read backend/.env if present

# --- LLM provider / model -------------------------------------------------
# Groq, free tier (30 req/min, ~14.4k req/day). We use one production model for
# all agents. llama-3.3-70b-versatile is a *production* model (not preview, so
# it won't get deprecated mid-hackathon), supports JSON / structured output
# which PydanticAI needs, and has a 128K context window.
#
# PydanticAI talks to Groq via the OpenAI-compatible endpoint, hence the
# "groq:" prefix it understands, or we pass the base_url explicitly in Stage 2.
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Lightweight fallback for cheap agents if we hit rate limits (also free-tier).
GROQ_MODEL_FAST = os.getenv("GROQ_MODEL_FAST", "llama-3.1-8b-instant")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# --- Free-tier protection -------------------------------------------------
# Every agent run is bound by a PydanticAI UsageLimits so a runaway loop can't
# burn the daily quota. request_limit caps LLM calls per agent run.
AGENT_REQUEST_LIMIT = int(os.getenv("AGENT_REQUEST_LIMIT", "3"))

# Hard cap on Evaluator re-query loops, independent of the LLM limit, so the
# orchestrator itself can never spin forever.
MAX_EVALUATOR_LOOPS = int(os.getenv("MAX_EVALUATOR_LOOPS", "2"))

# --- RAG (Stage 6) --------------------------------------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
RAG_DEFAULT_K = int(os.getenv("RAG_DEFAULT_K", "5"))

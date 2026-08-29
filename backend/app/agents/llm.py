"""
Shared LLM plumbing for every agent.

One place builds the Groq-backed PydanticAI model and the UsageLimits, so:
- the model string is set once (config.GROQ_MODEL), and
- every agent run is bound by the SAME free-tier protection.

Why a factory instead of a module-level Agent: each agent (router, gate, etc.)
has its own output_type and system prompt, so they construct their own Agent in
Stage 3. This module just hands them a ready-to-use Model + UsageLimits so the
Groq wiring lives in exactly one file.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_ai.models.groq import GroqModel
from pydantic_ai.providers.groq import GroqProvider
from pydantic_ai.usage import UsageLimits

from app import config


@lru_cache(maxsize=2)
def get_model(fast: bool = False) -> GroqModel:
    """Return a cached Groq model.

    fast=True selects the cheaper llama-3.1-8b-instant for lightweight agents
    (e.g. Doc Preparer) so we spend less of the free-tier quota on simple work.
    Cached so we don't rebuild the provider/HTTP client on every agent run.
    """
    model_name = config.GROQ_MODEL_FAST if fast else config.GROQ_MODEL
    provider = GroqProvider(api_key=config.GROQ_API_KEY)
    return GroqModel(model_name, provider=provider)


def usage_limits() -> UsageLimits:
    """The per-agent-run cap that protects the free-tier quota.

    request_limit bounds how many LLM HTTP calls a single agent.run() may make.
    A misbehaving agent that keeps retrying tools can't blow the daily quota.
    """
    return UsageLimits(request_limit=config.AGENT_REQUEST_LIMIT)

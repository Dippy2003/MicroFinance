"""
Shared helpers for the LLM agents.

Two things every agent needs and should NOT re-implement:
  1. run_agent(): run a PydanticAI Agent bound by our free-tier UsageLimits and
     return the typed output, tracing the call.
  2. A consistent failure story: if Groq errors or the run hits the usage limit,
     we don't crash the whole pipeline; we trace the failure and let the caller
     apply a deterministic fallback. For a hackathon demo, a degraded-but-alive
     pipeline beats a 500.
"""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel
from pydantic_ai import Agent

from app.agents.llm import usage_limits
from app.trace import Tracer

T = TypeVar("T", bound=BaseModel)


class AgentRunError(Exception):
    """Raised when an agent run fails (Groq error or usage-limit exceeded)."""


async def run_agent(
    agent: Agent,
    prompt: str,
    output_type: type[T],
    tracer: Tracer,
    actor: str,
) -> T:
    """Run `agent` on `prompt`, return its typed output, or raise AgentRunError.

    output_type is passed per-run so one Agent object can be reused; usage_limits
    is our free-tier guard (request_limit from config). We trace both the attempt
    and any failure so the trace tells the full story even on the unhappy path.
    """
    try:
        result = await agent.run(
            prompt,
            output_type=output_type,
            usage_limits=usage_limits(),
        )
        return result.output
    except Exception as exc:  # noqa: BLE001 - we deliberately catch all to degrade gracefully
        tracer.step(actor, f"LLM call failed ({type(exc).__name__}); using fallback.")
        raise AgentRunError(str(exc)) from exc

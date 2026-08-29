"""
Step implementations executed by the runner.

STAGE 3 real LLM agents:
Each function delegates to a PydanticAI agent (Groq) in app/agents/, reads the
agent's typed result and writes it into the shared `state`. The runner and these
function signatures are UNCHANGED from Stage 2; only the bodies now call real
agents. Every agent has its own deterministic fallback (in app/agents/), so a
Groq error degrades one step instead of crashing the pipeline.

`state` is the shared mutable dict carrying everything produced so far.
"""

from __future__ import annotations

from typing import Any

from app.agents.debt_advisor import advise_debt
from app.agents.doc_preparer import prepare_documents
from app.agents.eligibility_gate import check_eligibility
from app.agents.provider_matcher import match_providers
from app.agents.segment_router import route_segment
from app.orchestrator.plan import StepName
from app.trace import Tracer

State = dict[str, Any]


async def run_segment_router(state: State, tracer: Tracer) -> None:
    decision = await route_segment(state["profile"], tracer)
    state["segment_decision"] = decision


async def run_eligibility_gate(state: State, tracer: Tracer) -> None:
    segment = state["segment_decision"].segment
    result = await check_eligibility(state["profile"], segment, tracer)
    state["eligibility"] = result


async def run_provider_matcher(state: State, tracer: Tracer) -> None:
    segment = state["segment_decision"].segment
    matches = await match_providers(state["profile"], segment, tracer)
    state["matches"] = matches


async def run_doc_preparer(state: State, tracer: Tracer) -> None:
    segment = state["segment_decision"].segment
    docs = await prepare_documents(state["profile"], segment, tracer)
    state["documents"] = docs


async def run_debt_advisor(state: State, tracer: Tracer) -> None:
    segment = state["segment_decision"].segment
    advice = await advise_debt(state["profile"], segment, tracer)
    state["debt_advice"] = advice


# Map plan step names -> their implementation, so the runner stays generic.
STEP_IMPLEMENTATIONS = {
    StepName.SEGMENT_ROUTER: run_segment_router,
    StepName.ELIGIBILITY_GATE: run_eligibility_gate,
    StepName.PROVIDER_MATCHER: run_provider_matcher,
    StepName.DOC_PREPARER: run_doc_preparer,
    StepName.DEBT_ADVISOR: run_debt_advisor,
}

"""
Segment Router agent.

Classifies a BorrowerProfile into a Segment. This is general by design: it can
return any Segment, but for the demo only INFORMAL_VENDOR and MICRO_BUSINESS are
built deep downstream.

Output is the FROZEN SegmentDecision model, so PydanticAI forces the LLM to
return {segment, confidence, reasoning}; invalid output fails validation rather
than flowing downstream.
"""

from __future__ import annotations

from pydantic_ai import Agent

from app.agents.base import run_agent
from app.agents.llm import get_model
from app.models import BorrowerProfile, Segment, SegmentDecision
from app.trace import Tracer

# fast=True: classification is light, so we use the cheaper 8B model to save
# free-tier quota for the heavier matcher/advisor agents.
_SYSTEM_PROMPT = """\
You are the Segment Router for a Sri Lankan micro-loan advisory system.
Classify the borrower into exactly ONE segment so the right lending logic runs.

Segments:
- informal_vendor: street/market traders, home-based sellers, daily-income
  micro-entrepreneurs WITHOUT business registration. They go to microfinance.
- micro_business: a registered or semi-formal small business (a shop, workshop,
  service business) with business registration or clear business operations.
  They go to banks / finance-company SME loans.
- farmer: primarily agricultural cultivation/livestock income.
- salaried_low_income: earns a regular salary/wage from an employer.
- unknown: not enough information to classify confidently.

Decide from occupation, business registration, notes and income pattern.
Set confidence in [0,1]. If signals conflict or are thin, lower the confidence
and explain. Keep reasoning to one or two plain sentences a loan officer could
read aloud."""

_router_agent = Agent(
    get_model(fast=True),
    system_prompt=_SYSTEM_PROMPT,
)


def _format_profile(profile: BorrowerProfile) -> str:
    """Render the profile as a compact, LLM-friendly block."""
    return (
        f"Name: {profile.name}\n"
        f"Occupation: {profile.occupation}\n"
        f"Has business registration: {profile.has_business_registration}\n"
        f"Has bank account: {profile.has_bank_account}\n"
        f"Months in operation: {profile.months_in_operation}\n"
        f"Monthly income (LKR): {profile.monthly_income_lkr}\n"
        f"Loan purpose: {profile.loan_purpose}\n"
        f"Notes: {profile.notes}"
    )


async def route_segment(profile: BorrowerProfile, tracer: Tracer) -> SegmentDecision:
    """LLM segment classification with a deterministic fallback.

    If the LLM call fails (Groq error / usage limit), fall back to a simple,
    explainable rule so the pipeline still produces a usable segment.
    """
    prompt = f"Classify this borrower:\n\n{_format_profile(profile)}"
    try:
        decision = await run_agent(
            _router_agent, prompt, SegmentDecision, tracer, "SegmentRouter"
        )
    except Exception:
        # Fallback rule mirrors the Stage 2 placeholder so behaviour is known.
        text = f"{profile.occupation} {profile.notes or ''}".lower()
        if profile.has_business_registration or "shop" in text or "business" in text:
            segment = Segment.MICRO_BUSINESS
        else:
            segment = Segment.INFORMAL_VENDOR
        decision = SegmentDecision(
            segment=segment,
            confidence=0.4,
            reasoning="Fallback keyword rule (LLM unavailable).",
        )

    tracer.step(
        "SegmentRouter",
        f"Segment = {decision.segment.value} (conf {decision.confidence:.2f}): "
        f"{decision.reasoning}",
    )
    return decision

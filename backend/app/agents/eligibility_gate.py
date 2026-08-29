"""
Eligibility Gate agent.

Decides whether the borrower qualifies for this segment's loans. It reads the
REAL eligibility-norm chunks from RAG so the LLM judges against actual Sri
Lankan lending norms (e.g. BR + months in operation for SME loans), not its own
assumptions. This is the conditional gate: the runner skips the rest of the
pipeline when eligible == False.

Output is the FROZEN EligibilityResult: {eligible, reasoning, unmet_criteria}.
"""

from __future__ import annotations

from pydantic_ai import Agent

from app.agents.base import run_agent
from app.agents.llm import get_model
from app.models import BorrowerProfile, EligibilityResult, Segment
from app.rag.retriever import retrieve
from app.trace import Tracer

_SYSTEM_PROMPT = """\
You are the Eligibility Gate for a Sri Lankan micro-loan advisory system.
Given a borrower and the relevant eligibility NORMS retrieved from a knowledge
base, decide whether the borrower is plausibly eligible for loans in their
segment.

Requirements are SEGMENT-RELATIVE. Apply only the norms for THIS segment:
- informal_vendor -> MICROFINANCE. A formal business registration and a bank
  account are NOT required; do not reject for missing them. What matters is an
  existing income-generating activity and the ability to repay. Assume a valid
  NIC unless the profile contradicts it.
- micro_business -> BANK / FINANCE-COMPANY SME loans. Here business
  registration, some operating history, and a bank account ARE typically
  required.

AFFORDABILITY (read carefully):
- 'Existing debt' is an OUTSTANDING BALANCE, not a monthly payment. Do NOT
  subtract the whole balance from monthly income.
- You are given the borrower's MONTHLY SURPLUS (income minus expenses). Judge
  affordability by whether the ESTIMATED monthly repayment of the new loan fits
  within that surplus. A new loan is normally repaid over MANY months/years, so
  the monthly repayment is a SMALL FRACTION of the requested amount, not the
  whole amount. As a rough guide, a loan repaid over 1-5 years costs very
  roughly 2%-9% of the principal per month; if even a conservative estimate of
  that fits comfortably within the surplus, repayment capacity is satisfied.
- Only flag repayment capacity as unmet if the surplus clearly cannot cover a
  reasonable monthly repayment.

Rules:
- Judge ONLY against the provided norms for this segment plus the affordability
  guidance above.
- Be inclusive, not punitive: this product exists for the underbanked. Never
  invent a requirement that the segment's norms do not state. A missing
  'nice to have' is not a disqualifier; a missing HARD requirement is.
- If the borrower fails, list each unmet criterion as a short, actionable item
  (what they would need to do/obtain), so a 'no' is a path forward.
- eligible is a strict boolean. Keep reasoning to one or two plain sentences."""

_gate_agent = Agent(
    get_model(),  # full 70B: eligibility is a judgement call worth the better model
    system_prompt=_SYSTEM_PROMPT,
)


async def check_eligibility(
    profile: BorrowerProfile, segment: Segment, tracer: Tracer
) -> EligibilityResult:
    """LLM eligibility judgement against retrieved norms, with a safe fallback."""
    # Retrieve eligibility-norm chunks for this segment.
    norm_chunks = retrieve("eligibility requirements norms", segment.value, k=5)
    norms_text = "\n".join(f"- {c.text} (source: {c.source})" for c in norm_chunks)
    tracer.step(
        "EligibilityGate",
        f"Loaded {len(norm_chunks)} eligibility-norm chunk(s) from RAG.",
    )

    # Pre-compute the monthly surplus so the LLM judges affordability against a
    # correct number instead of re-deriving (and mis-deriving) it.
    income = profile.monthly_income_lkr or 0
    expenses = profile.monthly_expenses_lkr or 0
    surplus = income - expenses

    prompt = (
        f"Segment: {segment.value}\n\n"
        f"Borrower:\n"
        f"- Occupation: {profile.occupation}\n"
        f"- Monthly income (LKR): {profile.monthly_income_lkr}\n"
        f"- Monthly expenses (LKR): {profile.monthly_expenses_lkr}\n"
        f"- Monthly surplus (income - expenses, LKR): {surplus:,.0f}\n"
        f"- Existing debt OUTSTANDING BALANCE (LKR, not a monthly payment): "
        f"{profile.existing_debt_lkr}\n"
        f"- Requested loan amount (LKR, repaid over months/years): "
        f"{profile.requested_amount_lkr}\n"
        f"- Has business registration: {profile.has_business_registration}\n"
        f"- Has bank account: {profile.has_bank_account}\n"
        f"- Months in operation: {profile.months_in_operation}\n\n"
        f"Eligibility norms:\n{norms_text or '(none retrieved)'}\n\n"
        f"Decide eligibility."
    )

    try:
        result = await run_agent(
            _gate_agent, prompt, EligibilityResult, tracer, "EligibilityGate"
        )
    except Exception:
        # Deterministic fallback: require some income, and a toy affordability
        # check, mirroring Stage 2 so the demo never dead-ends on a Groq blip.
        unmet: list[str] = []
        if not profile.monthly_income_lkr:
            unmet.append("Provide a monthly income figure.")
        if (
            profile.requested_amount_lkr
            and profile.monthly_income_lkr
            and profile.monthly_income_lkr < 0.10 * profile.requested_amount_lkr
        ):
            unmet.append("Requested amount is large relative to monthly income.")
        result = EligibilityResult(
            eligible=not unmet,
            reasoning="Fallback affordability check (LLM unavailable).",
            unmet_criteria=unmet,
        )

    verdict = "ELIGIBLE" if result.eligible else "NOT eligible"
    tracer.step("EligibilityGate", f"{verdict}: {result.reasoning}")
    for u in result.unmet_criteria:
        tracer.step("EligibilityGate", f"  - unmet: {u}")
    return result

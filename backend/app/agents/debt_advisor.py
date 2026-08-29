"""
Debt Advisor agent.

Gives the borrower short, responsible affordability advice: can they comfortably
service the requested loan given income, expenses and existing debt, and what to
watch (e.g. the CBSL 35% all-in microfinance rate cap). This is a
consumer-protection touch that plays well with judges and is genuinely useful.

Output: a short advice string wrapped in a model. We compute the surplus
deterministically and hand it to the LLM so the numbers are correct and the LLM
only does the phrasing/judgement.
"""

from __future__ import annotations

from pydantic import BaseModel
from pydantic_ai import Agent

from app.agents.base import run_agent
from app.agents.llm import get_model
from app.models import BorrowerProfile, Segment
from app.rag.retriever import retrieve
from app.trace import Tracer


class _Advice(BaseModel):
    advice: str


_SYSTEM_PROMPT = """\
You are the Debt Advisor for a Sri Lankan micro-loan advisory system.
Give brief, responsible borrowing advice for THIS borrower.

Rules:
- Use the pre-computed monthly surplus figure given to you; do not recompute.
- Comment on whether the requested loan looks affordable and what repayment
  level stays safe (keep total repayments well within surplus).
- If the retrieved context mentions an interest-rate cap (e.g. CBSL 35% all-in
  for microfinance), remind the borrower to compare the all-in rate.
- 2-3 sentences, plain language, supportive not preachy. No markdown."""

_advisor_agent = Agent(
    get_model(),  # full 70B: this is the user-facing advice, worth the better model
    system_prompt=_SYSTEM_PROMPT,
)


async def advise_debt(
    profile: BorrowerProfile, segment: Segment, tracer: Tracer
) -> str:
    """LLM affordability advice over deterministic numbers, with a fallback."""
    income = profile.monthly_income_lkr or 0
    expenses = profile.monthly_expenses_lkr or 0
    debt = profile.existing_debt_lkr or 0
    surplus = income - expenses

    context_chunks = retrieve("interest rate cap repayment", segment.value, k=2)
    context_text = "\n".join(f"- {c.text}" for c in context_chunks)

    prompt = (
        f"Monthly income: LKR {income:,.0f}\n"
        f"Monthly expenses: LKR {expenses:,.0f}\n"
        f"Pre-computed monthly surplus: LKR {surplus:,.0f}\n"
        f"Existing debt: LKR {debt:,.0f}\n"
        f"Requested loan: LKR {profile.requested_amount_lkr or 0:,.0f}\n\n"
        f"Context:\n{context_text or '(none)'}\n\n"
        f"Give affordability advice."
    )

    try:
        result = await run_agent(_advisor_agent, prompt, _Advice, tracer, "DebtAdvisor")
        advice = result.advice
    except Exception:
        advice = (
            f"Monthly surplus before any new repayment is about LKR {surplus:,.0f}. "
            f"Keep total loan repayments well within that surplus, and compare the "
            f"all-in interest rate (CBSL caps microfinance at 35% p.a. inclusive of "
            f"charges)."
        )

    tracer.step("DebtAdvisor", advice)
    return advice

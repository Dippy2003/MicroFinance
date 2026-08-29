"""
FROZEN shared Pydantic contracts for the MicroLoan AI Agent.

Everything in the system (agents, orchestrator, FastAPI, frontend) is built
against these models. Per the hackathon brief, DO NOT change these shapes
without an explicit decision, because the planner, evaluator, API responses and
the Next.js frontend all depend on them.

Design notes:
- We keep these models intentionally small and flat so they are easy to explain
  under questioning and easy to serialize to JSON for the SSE stream and the
  POST /advise response.
- `Segment` is an Enum so the router can only ever produce a known segment, and
  so adding a third segment later is a one-line change in a single place.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Segment(str, Enum):
    """The borrower segments our architecture knows about.

    We build INFORMAL_VENDOR and MICRO_BUSINESS deep for the demo, but the
    enum also lists the segments our architecture is meant to *route* to, so
    the router's output type already covers the general case.
    """

    INFORMAL_VENDOR = "informal_vendor"   # Segment A -> microfinance providers
    MICRO_BUSINESS = "micro_business"      # Segment B -> bank / finance-company loans
    FARMER = "farmer"                      # routed but not built deep (demo)
    SALARIED_LOW_INCOME = "salaried_low_income"  # routed but not built deep (demo)
    UNKNOWN = "unknown"                    # router could not classify confidently


class Chunk(BaseModel):
    """A single retrieved RAG chunk.

    This is the return shape of retrieve(). Kept to exactly {text, source} so
    the retriever can be swapped from stub -> pgvector (Stage 6) without
    touching any caller.
    """

    text: str
    source: str


class BorrowerProfile(BaseModel):
    """The applicant. This is the single input to the whole pipeline.

    Fields are deliberately broad enough to describe ANY segment; segment-
    specific agents read the subset they care about. `monthly_income_lkr` is
    the value the Evaluator watches for changes to trigger a re-query loop.
    """

    name: str
    age: int | None = None
    district: str | None = Field(default=None, description="Sri Lankan district, e.g. 'Gampaha'")
    occupation: str = Field(description="Free-text occupation, used by the Segment Router")

    # Financial signals (all optional so partial profiles still flow through)
    monthly_income_lkr: float | None = Field(default=None, ge=0)
    monthly_expenses_lkr: float | None = Field(default=None, ge=0)
    existing_debt_lkr: float | None = Field(default=None, ge=0)

    # Loan ask
    requested_amount_lkr: float | None = Field(default=None, ge=0)
    loan_purpose: str | None = None

    # Soft eligibility signals
    has_bank_account: bool | None = None
    has_business_registration: bool | None = None
    months_in_operation: int | None = Field(default=None, ge=0)

    # Free-text hint the router/segment logic can use
    notes: str | None = None


class SegmentDecision(BaseModel):
    """Output of the Segment Router agent."""

    segment: Segment
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class EligibilityResult(BaseModel):
    """Output of the conditional Eligibility Gate.

    `eligible` gates the rest of the pipeline: Provider Matcher runs ONLY when
    this is True. `unmet_criteria` is surfaced to the borrower so a 'no' is
    actionable rather than a dead end.
    """

    eligible: bool
    reasoning: str
    unmet_criteria: list[str] = Field(default_factory=list)


class ProviderMatch(BaseModel):
    """A single ranked loan provider recommendation.

    Produced by the Provider Matcher from retrieved RAG chunks. `score` drives
    ranking; `source` lets us cite where the provider info came from (trust +
    defensibility during judging).

    The fields below `source` are an ADDITIVE extension (Stage 4): all optional
    with defaults, so existing callers/tests stay valid. They give the frontend
    structured, comparable columns (a real comparison table) instead of having
    to parse the free-text `indicative_terms`. `is_recommended` flags the single
    best match per run so the UI can highlight one clear pick.
    """

    provider_name: str
    product_name: str | None = None
    score: float = Field(ge=0.0, le=1.0, description="Match score used for ranking")
    rationale: str
    indicative_terms: str | None = Field(
        default=None, description="e.g. interest range, max amount, tenure"
    )
    source: str = Field(description="Citation back to the RAG source")

    # --- Additive comparison fields (Stage 4) ---
    interest_rate: str | None = Field(
        default=None, description="Indicative interest, e.g. '10-12.5% p.a.'"
    )
    max_amount_lkr: float | None = Field(
        default=None, ge=0, description="Indicative maximum loan amount in LKR"
    )
    tenure: str | None = Field(
        default=None, description="Indicative repayment tenure, e.g. '12-24 months'"
    )
    key_requirement: str | None = Field(
        default=None, description="The single most important eligibility requirement"
    )
    is_recommended: bool = Field(
        default=False, description="True for the single top recommended match"
    )


class Verdict(str, Enum):
    """The Evaluator's terminal decision for a run."""

    DONE = "done"            # pipeline produced a usable result
    LOOP = "loop"            # re-plan / re-rank needed (e.g. income changed)
    ESCALATE = "escalate"    # cannot help automatically -> human / not eligible


class AdviceResponse(BaseModel):
    """The POST /advise response body. Matches the frozen API contract:
    {verdict, matches, trace}.
    """

    verdict: Verdict
    matches: list[ProviderMatch] = Field(default_factory=list)
    trace: list[str] = Field(default_factory=list)

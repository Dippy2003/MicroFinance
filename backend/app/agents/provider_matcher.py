"""
Provider Matcher agent.

Retrieves provider chunks from RAG for the segment, then asks the LLM to rank
the providers against THIS borrower and justify each with a rationale, citing
the source chunk. Output is a list of the FROZEN ProviderMatch model.

We pass the retrieved providers explicitly and instruct the LLM to ONLY use
them, so it cannot invent a lender. Every match must carry a `source` from the
provided chunks, which is what makes the recommendation defensible.

COMPARISON (Stage 4): the LLM also fills structured comparable fields
(interest_rate, max_amount_lkr, tenure, key_requirement) so the frontend can
render a side-by-side comparison table. The single 'recommended' pick is decided
by OUR code (highest score), not left to the LLM, so the recommendation is
deterministic and explainable.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from app.agents.base import run_agent
from app.agents.llm import get_model
from app.models import BorrowerProfile, ProviderMatch, Segment
from app.rag.retriever import retrieve
from app.trace import Tracer


class _MatchList(BaseModel):
    """Wrapper so the LLM returns a structured list of matches.

    PydanticAI output types are models; we wrap list[ProviderMatch] in a model
    with one field and unwrap it. Keeps ProviderMatch itself frozen/unchanged.
    """

    matches: list[ProviderMatch] = Field(default_factory=list)


_SYSTEM_PROMPT = """\
You are the Provider Matcher for a Sri Lankan micro-loan advisory system.
You are given a borrower and a list of CANDIDATE PROVIDERS retrieved from a
knowledge base. Rank the providers for THIS borrower and explain each.

Strict rules:
- Use ONLY the candidate providers given. NEVER invent a provider, product,
  rate, or amount that is not supported by the candidate text.
- For each recommended provider produce these fields, and DO NOT confuse them:
    * provider_name: the lender's name only (e.g. "LOLC Finance PLC").
    * product_name: the loan/product name if stated, else null.
    * score: a number in [0,1] (higher = better fit).
    * rationale: ONE sentence tying the fit to the borrower's situation.
    * indicative_terms: a short free-text summary of amounts/rates/tenure.
    * source: copy VERBATIM the string after "(source: ...)" for that candidate.
      This is a short citation like "lolcfinance.com/... (2026)"; NEVER put the
      provider's description text in the source field.
  Also fill these COMPARISON fields from the candidate text (use null if the
  candidate does not state it, do NOT guess):
    * interest_rate: e.g. "10-12.5% p.a." or "AWPLR + 2.5%".
    * max_amount_lkr: the maximum loan amount as a NUMBER in LKR (e.g. 300000).
    * tenure: e.g. "12-24 months" or "up to 5 years".
    * key_requirement: the single most important eligibility requirement
      (e.g. "Business Registration" or "Existing trade + NIC").
- Leave is_recommended as false; the system sets the recommended pick itself.
- Return them ordered best-first. Recommend at most 3. If none fit, return an
  empty list."""

_matcher_agent = Agent(
    get_model(),  # full 70B: ranking + justification benefits from the better model
    system_prompt=_SYSTEM_PROMPT,
)


async def match_providers(
    profile: BorrowerProfile, segment: Segment, tracer: Tracer
) -> list[ProviderMatch]:
    """Retrieve providers, LLM-rank them, fall back to raw RAG order on failure."""
    query = profile.loan_purpose or profile.occupation
    chunks = retrieve(query, segment.value, k=5)
    provider_chunks = [c for c in chunks if c.text.startswith("Provider:")]
    tracer.step(
        "ProviderMatcher",
        f"Retrieved {len(chunks)} chunk(s); {len(provider_chunks)} are providers.",
    )

    candidates = "\n\n".join(
        f"[{i+1}] {c.text}\n(source: {c.source})"
        for i, c in enumerate(provider_chunks)
    )
    prompt = (
        f"Borrower: {profile.occupation}, monthly income LKR "
        f"{profile.monthly_income_lkr}, wants LKR {profile.requested_amount_lkr} "
        f"for: {profile.loan_purpose}.\n\n"
        f"Candidate providers:\n{candidates or '(none)'}\n\n"
        f"Rank and justify the best matches."
    )

    try:
        result = await run_agent(
            _matcher_agent, prompt, _MatchList, tracer, "ProviderMatcher"
        )
        matches = result.matches
    except Exception:
        # Fallback: turn the top provider chunks into matches in RAG order so the
        # demo still shows real, cited providers even if the LLM is unavailable.
        matches = []
        for i, c in enumerate(provider_chunks[:3]):
            name = c.text.split(".")[0].replace("Provider:", "").strip()
            matches.append(
                ProviderMatch(
                    provider_name=name,
                    score=round(1.0 - i * 0.15, 2),
                    rationale="Fallback: top RAG match (LLM unavailable).",
                    source=c.source,
                )
            )

    matches = _rank_and_recommend(matches, tracer)
    return matches


def _rank_and_recommend(
    matches: list[ProviderMatch], tracer: Tracer
) -> list[ProviderMatch]:
    """Deterministically sort by score (best-first) and flag the top pick.

    The LLM scores and describes; OUR code decides the ordering and the single
    recommendation. This keeps the recommendation reproducible and easy to
    defend ('we recommend the highest-scoring eligible match'), independent of
    whatever order the LLM happened to return.
    """
    if not matches:
        tracer.step("ProviderMatcher", "No provider matches produced.")
        return matches

    ranked = sorted(matches, key=lambda m: m.score, reverse=True)
    # Reset then set the single recommended flag (top score wins).
    for m in ranked:
        m.is_recommended = False
    ranked[0].is_recommended = True

    tracer.step(
        "ProviderMatcher",
        f"Ranked {len(ranked)} match(es); recommending '{ranked[0].provider_name}'.",
    )
    for m in ranked:
        star = " ⭐RECOMMENDED" if m.is_recommended else ""
        rate = m.interest_rate or "rate n/a"
        cap = f"max LKR {m.max_amount_lkr:,.0f}" if m.max_amount_lkr else "max n/a"
        tracer.step(
            "ProviderMatcher",
            f"  - {m.provider_name} (score {m.score}) - {rate}, {cap} "
            f"[{m.source}]{star}",
        )
    return ranked

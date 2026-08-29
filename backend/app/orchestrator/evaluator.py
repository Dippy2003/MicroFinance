"""
The Evaluator.

Responsibility: after a run through the plan, decide the terminal Verdict
(done / loop / escalate) and narrate why. It does NOT execute steps; it judges
the resulting state.

DECISION TABLE:
  - NOT eligible                         -> ESCALATE (could not place borrower)
  - eligible but 0 matches               -> ESCALATE (no provider found)
  - eligible, matches, income just
    changed and not yet re-ranked, and
    loop budget remains                  -> LOOP  (re-plan + re-rank, Stage 5)
  - eligible with matches                -> DONE

The LOOP branch is what fires when the borrower's income changes after a first
result: the orchestrator must re-rank providers against the new income before
finishing. We bound it with a loop budget so it can never spin (also enforced by
the runner).
"""

from __future__ import annotations

from typing import Any

from app.models import Verdict
from app.trace import Tracer

State = dict[str, Any]


def evaluate(state: State, tracer: Tracer) -> Verdict:
    """Inspect run state and return the terminal verdict.

    Reads two loop-control flags the runner sets on `state`:
      - 'pending_income_rerank': True after an income change until we re-rank.
      - 'loops_remaining': how many re-query loops are still permitted.
    """
    eligibility = state.get("eligibility")
    matches = state.get("matches", [])

    if eligibility is not None and not eligibility.eligible:
        tracer.step(
            "Evaluator",
            "Verdict = ESCALATE: borrower did not pass the eligibility gate.",
        )
        return Verdict.ESCALATE

    if not matches:
        tracer.step(
            "Evaluator",
            "Verdict = ESCALATE: eligible but no provider match was found.",
        )
        return Verdict.ESCALATE

    # LOOP: income changed since the last ranking and we still have budget.
    pending_rerank = state.get("pending_income_rerank", False)
    loops_remaining = state.get("loops_remaining", 0)
    if pending_rerank and loops_remaining > 0:
        tracer.step(
            "Evaluator",
            "Verdict = LOOP: income changed since ranking, re-plan and re-rank "
            f"required ({loops_remaining} loop(s) left).",
        )
        return Verdict.LOOP

    tracer.step(
        "Evaluator",
        f"Verdict = DONE: eligible with {len(matches)} provider match(es).",
    )
    return Verdict.DONE

"""
The Planner.

Responsibility: look at the BorrowerProfile and produce a Plan (which steps to
run, serial vs parallel, and why). It does NOT execute anything.

STAGE 2 deterministic baseline planner:
We build the plan in plain Python, no LLM call. This is a deliberate choice:
  1. The orchestrator SPINE (execute plan -> trace -> evaluate) is what Stage 2
     is proving, and we want it runnable and testable without spending quota.
  2. A deterministic plan is the ground truth we can compare a future LLM
     planner against when judging "did the plan make sense".

The shape it returns (Plan) is identical to what an LLM planner will return, so
Stage 3 can swap `build_plan` for an LLM-backed version with no change to the
runner. The conditional nature of the Eligibility Gate is honoured here: the
Provider Matcher / Doc Preparer / Debt Advisor stages are still produced, but
the RUNNER skips everything after the gate when the borrower is ineligible (the
plan describes the happy path; the runner enforces the condition).
"""

from __future__ import annotations

from app.models import BorrowerProfile
from app.orchestrator.plan import Plan, Stage, StepName
from app.trace import Tracer


def build_plan(profile: BorrowerProfile, tracer: Tracer) -> Plan:
    """Produce the execution plan for a profile and narrate it into the trace."""
    plan = Plan(
        rationale=(
            "Classify the borrower first, gate on eligibility, then (only if "
            "eligible) match providers, and finally prepare docs and debt "
            "advice in parallel since they are independent."
        ),
        stages=[
            Stage(
                steps=[StepName.SEGMENT_ROUTER],
                why="Must know the segment before any segment-specific logic.",
            ),
            Stage(
                steps=[StepName.ELIGIBILITY_GATE],
                why="Conditional gate: stop here if the borrower does not qualify.",
            ),
            Stage(
                steps=[StepName.PROVIDER_MATCHER],
                why="Rank providers via RAG, only reached when eligible.",
            ),
            Stage(
                steps=[StepName.DOC_PREPARER, StepName.DEBT_ADVISOR],
                why="Independent of each other, so run them in parallel.",
            ),
        ],
    )

    tracer.step("Planner", f"Built plan with {len(plan.stages)} stage(s).")
    tracer.step("Planner", f"Rationale: {plan.rationale}")
    for i, stage in enumerate(plan.stages, start=1):
        names = ", ".join(s.value for s in stage.steps)
        parallel = " (parallel)" if len(stage.steps) > 1 else ""
        tracer.step("Planner", f"Stage {i}: {names}{parallel} - {stage.why}")

    return plan

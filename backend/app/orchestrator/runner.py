"""
The Runner: executes a Plan.

This is the "my application code executes it" half of explicit orchestration.
The planner handed us a Plan (data). Here we walk it:

  - Stages run SERIALLY (one after another).
  - Steps WITHIN a stage run in PARALLEL via asyncio.gather.
  - The Eligibility Gate is CONDITIONAL: after the gate stage runs, if the
    borrower is not eligible we STOP: we do not run the Provider Matcher,
    Doc Preparer or Debt Advisor. This is enforced HERE, by our code, not by
    the LLM, which is the whole point.

The runner is generic: it maps each StepName to its implementation via
STEP_IMPLEMENTATIONS and never hard-codes a specific agent, so adding/removing
steps is a planner concern, not a runner change.

RE-QUERY LOOP (Stage 5):
After a pass, the Evaluator may return LOOP, meaning the borrower's income
changed and providers must be re-ranked against the new figure. The runner then
applies the new income, re-plans, and runs another pass, decrementing a loop
budget (config.MAX_EVALUATOR_LOOPS) so it can never spin forever. Each pass and
the income change are written to the SAME trace, so the whole re-query story is
visible end-to-end.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app import config
from app.models import AdviceResponse, BorrowerProfile, ProviderMatch, Verdict
from app.orchestrator.evaluator import evaluate
from app.orchestrator.plan import StepName
from app.orchestrator.planner import build_plan
from app.orchestrator.steps import STEP_IMPLEMENTATIONS
from app.trace import Tracer

State = dict[str, Any]


async def _run_stage(steps: list[StepName], state: State, tracer: Tracer) -> None:
    """Run all steps in one stage in parallel."""
    coros = [STEP_IMPLEMENTATIONS[step](state, tracer) for step in steps]
    # asyncio.gather runs the agents concurrently. This is what makes
    # Doc Preparer + Debt Advisor (one stage) overlap.
    await asyncio.gather(*coros)


async def _run_one_pass(profile: BorrowerProfile, state: State, tracer: Tracer) -> None:
    """Plan and execute a single pass over the pipeline (with conditional gate).

    Writes results into `state`. Factored out so the re-query loop can call it
    again after an income change without duplicating the plan/execute logic.
    """
    plan = build_plan(profile, tracer)
    for i, stage in enumerate(plan.stages, start=1):
        names = ", ".join(s.value for s in stage.steps)
        tracer.step("Orchestrator", f"Running stage {i}: {names}.")
        await _run_stage(stage.steps, state, tracer)

        # CONDITIONAL GATE: stop this pass if the gate just rejected.
        if StepName.ELIGIBILITY_GATE in stage.steps:
            eligibility = state.get("eligibility")
            if eligibility is not None and not eligibility.eligible:
                tracer.step(
                    "Orchestrator",
                    "Eligibility gate failed: skipping remaining stages.",
                )
                break


async def run_pipeline(
    profile: BorrowerProfile,
    income_change_to: float | None = None,
    tracer: Tracer | None = None,
) -> AdviceResponse:
    """Plan -> execute -> evaluate, with an optional income-change re-query loop.

    Returns the frozen {verdict, matches, trace} contract.

    income_change_to: if given, after the first pass the orchestrator updates the
    borrower's monthly income to this value and re-plans/re-ranks. Left None
    (default) the behaviour is identical to before, a single pass. This keeps
    the POST /advise contract unchanged while enabling the Stage 5 demo.

    tracer: an optional pre-built Tracer. The SSE endpoint passes one with an
    on_append callback so trace lines stream live as they are produced. When
    None (the default, e.g. POST /advise and the CLI) we create our own.
    """
    if tracer is None:
        tracer = Tracer()
    tracer.step("Orchestrator", f"Starting advice run for '{profile.name}'.")

    state: State = {
        "profile": profile,
        # Loop control: we permit at most MAX_EVALUATOR_LOOPS re-query passes.
        "loops_remaining": config.MAX_EVALUATOR_LOOPS,
        "pending_income_rerank": False,
    }

    # FIRST PASS
    await _run_one_pass(profile, state, tracer)
    verdict = evaluate(state, tracer)

    # If an income change was requested and the first pass produced a usable
    # result, arm the re-rank so the Evaluator returns LOOP on the next check.
    if income_change_to is not None and verdict == Verdict.DONE:
        old = profile.monthly_income_lkr
        tracer.step(
            "Orchestrator",
            f"Income change reported: LKR {old or 0:,.0f} -> LKR {income_change_to:,.0f}.",
        )
        profile.monthly_income_lkr = income_change_to
        state["pending_income_rerank"] = True
        verdict = evaluate(state, tracer)  # should now be LOOP

    # RE-QUERY LOOP: while the Evaluator says LOOP and we have budget, re-run.
    while verdict == Verdict.LOOP and state["loops_remaining"] > 0:
        state["loops_remaining"] -= 1
        tracer.step(
            "Orchestrator",
            f"Re-query loop: re-planning and re-ranking on new income "
            f"(loop {config.MAX_EVALUATOR_LOOPS - state['loops_remaining']}).",
        )
        await _run_one_pass(profile, state, tracer)
        # The re-rank is now done; clear the flag so the next evaluate ends it.
        state["pending_income_rerank"] = False
        verdict = evaluate(state, tracer)

    matches: list[ProviderMatch] = state.get("matches", [])
    return AdviceResponse(verdict=verdict, matches=matches, trace=tracer.lines)

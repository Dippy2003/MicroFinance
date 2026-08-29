"""
The execution Plan: the structured output of the Planner agent.

This is the heart of "explicit orchestration, NOT native tool-calling". The
planner does NOT call tools itself. It returns a Plan, plain data describing
which steps to run, in what order, and which may run in parallel, and OUR code
(orchestrator/runner.py) executes that data. This separation is what we defend
under questioning: the LLM proposes, application code disposes.

A Plan is an ordered list of Stages. Steps WITHIN a stage run in parallel
(asyncio.gather); stages run serially, one after another. That maps directly to
the architecture: e.g. Doc Preparer + Debt Advisor are two steps in one stage
(parallel), while Eligibility Gate is its own earlier stage (must finish first).
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class StepName(str, Enum):
    """The fixed catalogue of steps the planner may schedule.

    Using an Enum (not free-text) means the planner can only ever name a step
    our runner knows how to execute; an unknown step fails validation instead
    of silently doing nothing.
    """

    SEGMENT_ROUTER = "segment_router"
    ELIGIBILITY_GATE = "eligibility_gate"
    PROVIDER_MATCHER = "provider_matcher"
    DOC_PREPARER = "doc_preparer"
    DEBT_ADVISOR = "debt_advisor"


class Stage(BaseModel):
    """One serial stage. All steps inside run in parallel."""

    steps: list[StepName] = Field(min_length=1)
    why: str = Field(description="One-line reason this stage runs when it does.")


class Plan(BaseModel):
    """The full execution plan produced by the planner."""

    stages: list[Stage] = Field(min_length=1)
    rationale: str = Field(
        description="Overall reasoning: why this ordering / parallelism."
    )

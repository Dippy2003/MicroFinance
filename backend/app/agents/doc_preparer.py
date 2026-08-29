"""
Doc Preparer agent.

Produces the document checklist the borrower needs for their segment's loans.
Reads RAG (eligibility/provider chunks mention required documents) so the list
reflects real Sri Lankan requirements (NIC, Business Registration, bank
statements, proof of trade, etc.).

Output: a simple list[str] of checklist items, wrapped in a model for PydanticAI.
Uses the fast 8B model: this is a light, well-bounded task.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from app.agents.base import run_agent
from app.agents.llm import get_model
from app.models import BorrowerProfile, Segment
from app.rag.retriever import retrieve
from app.trace import Tracer


class _DocList(BaseModel):
    documents: list[str] = Field(default_factory=list)


_SYSTEM_PROMPT = """\
You are the Document Preparer for a Sri Lankan micro-loan advisory system.
Given the borrower's segment and retrieved norms, output the concrete checklist
of documents they should gather to apply.

Rules:
- Base the list on the retrieved norms and standard Sri Lankan requirements.
- Be specific and local (e.g. 'Valid NIC', 'Business Registration (BR)',
  'Bank statements for the last 6-12 months', 'Proof of trade / income').
- Keep it short (3-6 items), each a single noun phrase. No commentary."""

_doc_agent = Agent(
    get_model(fast=True),
    system_prompt=_SYSTEM_PROMPT,
)


async def prepare_documents(
    profile: BorrowerProfile, segment: Segment, tracer: Tracer
) -> list[str]:
    """LLM document checklist with a segment-based fallback."""
    norm_chunks = retrieve("required documents eligibility", segment.value, k=4)
    norms_text = "\n".join(f"- {c.text}" for c in norm_chunks)
    prompt = (
        f"Segment: {segment.value}\n"
        f"Has business registration: {profile.has_business_registration}\n"
        f"Has bank account: {profile.has_bank_account}\n\n"
        f"Retrieved norms:\n{norms_text or '(none)'}\n\n"
        f"List the documents to gather."
    )

    try:
        result = await run_agent(_doc_agent, prompt, _DocList, tracer, "DocPreparer")
        docs = result.documents
    except Exception:
        if segment == Segment.MICRO_BUSINESS:
            docs = [
                "Valid NIC",
                "Business Registration (BR) / Certificate of Incorporation",
                "Business bank statements (last 6-12 months)",
                "Proof of business cash flow",
            ]
        else:
            docs = [
                "Valid NIC",
                "Proof of trade / income-generating activity",
                "Proof of residence in operating area",
            ]

    tracer.step("DocPreparer", f"Prepared {len(docs)} required document(s).")
    # Emit each document as its own trace line so the live trace and the frontend
    # can show the full checklist (the trace is the channel for this; the frozen
    # AdviceResponse stays {verdict, matches, trace}).
    for doc in docs:
        tracer.step("DocPreparer", f"  - {doc}")
    return docs

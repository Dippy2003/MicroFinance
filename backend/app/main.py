"""
FastAPI skeleton for the MicroLoan AI Agent.

FROZEN API contract:
    POST /advise        {profile} -> {verdict, matches, trace}
    GET  /advise/stream           -> SSE stream of trace lines

POST /advise runs the full orchestrator and returns the structured result.
GET /advise/stream runs the SAME orchestrator but streams each trace line live
(via the Tracer on_append callback) and ends with a final frame carrying the
verdict + matches, so the frontend can render the live trace and the result from
one request.

CORS is open to localhost so the Next.js dev server can call us.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.models import AdviceResponse, BorrowerProfile
from app.orchestrator.runner import run_pipeline
from app.trace import Tracer

app = FastAPI(title="MicroLoan AI Agent", version="0.1.0")

# Allow the Next.js dev server (and a generic localhost) to call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness check + a hello-world we can curl right now."""
    return {"status": "ok", "service": "microloan-ai-agent", "stage": "1"}


@app.post("/advise", response_model=AdviceResponse)
async def advise(
    profile: BorrowerProfile,
    income_change_to: float | None = None,
) -> AdviceResponse:
    """Run the full orchestrator and return {verdict, matches, trace}.

    The request BODY is the frozen BorrowerProfile contract. `income_change_to`
    is an OPTIONAL query parameter (not part of the body), so the frozen
    POST /advise {profile} contract is unchanged. When supplied, it triggers the
    Stage 5 re-query loop: the borrower's income is updated to this value after
    the first result and providers are re-ranked, all captured in `trace`.
    """
    return await run_pipeline(profile, income_change_to=income_change_to)


async def _advise_events(
    profile: BorrowerProfile, income_change_to: float | None
) -> AsyncGenerator[str, None]:
    """Run the orchestrator and yield SSE frames as the trace is produced.

    Mechanism:
      - An asyncio.Queue receives every trace line via the Tracer's on_append
        callback (called synchronously from inside the agents).
      - run_pipeline runs as a background task using that tracer.
      - This generator drains the queue, emitting one 'line' frame per trace
        line, until the task finishes; then it emits a final 'result' frame with
        the verdict + matches and a 'done' marker.
    Frame shapes (JSON after 'data: '):
      {"line": "..."}                          a trace line
      {"result": {...AdviceResponse...}}        final structured result
      {"done": true}                            stream end
      {"error": "..."}                          something failed
    """
    queue: asyncio.Queue[str] = asyncio.Queue()

    # on_append runs in the pipeline's coroutine; put_nowait is safe and non-blocking.
    tracer = Tracer(on_append=queue.put_nowait)

    task = asyncio.create_task(
        run_pipeline(profile, income_change_to=income_change_to, tracer=tracer)
    )

    # Stream lines until the pipeline task completes AND the queue is drained.
    while not task.done() or not queue.empty():
        try:
            line = await asyncio.wait_for(queue.get(), timeout=0.1)
            yield f"data: {json.dumps({'line': line})}\n\n"
        except asyncio.TimeoutError:
            # No new line yet; loop again to re-check task.done(). This keeps the
            # connection alive and responsive without busy-waiting.
            continue

    try:
        result: AdviceResponse = task.result()
        yield f"data: {json.dumps({'result': result.model_dump()})}\n\n"
    except Exception as exc:  # noqa: BLE001 - surface failures to the client
        yield f"data: {json.dumps({'error': f'{type(exc).__name__}: {exc}'})}\n\n"

    yield f"data: {json.dumps({'done': True})}\n\n"


@app.get("/advise/stream")
async def advise_stream(
    profile: str,
    income_change_to: float | None = None,
) -> StreamingResponse:
    """SSE endpoint: stream the live agent trace, then the final result.

    `profile` is a JSON-encoded BorrowerProfile passed as a query parameter,
    because EventSource (the browser SSE client) can only issue GET requests and
    cannot send a JSON body. We parse and validate it into the frozen
    BorrowerProfile model. `income_change_to` optionally triggers the re-query
    loop, exactly like POST /advise.
    """
    parsed = BorrowerProfile.model_validate_json(profile)
    return StreamingResponse(
        _advise_events(parsed, income_change_to),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

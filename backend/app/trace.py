"""
The trace: an append-only list of human-readable decision lines.

This is a FROZEN contract. The frontend renders these strings verbatim, and the
SSE endpoint streams them one per line. Keeping it a plain list[str] (not a rich
object) is deliberate: it's trivial to serialize, trivial to stream, and forces
every agent to explain its decision in plain language we can defend out loud.

`Tracer` is a thin wrapper that timestamps/prefixes lines consistently and lets
the orchestrator pass one shared trace through every agent.

LIVE STREAMING (Stage 7):
An optional `on_append` callback fires for every line as it is added. The SSE
endpoint uses this to push lines to the browser the moment they are produced,
while `lines` still holds the full append-only list for the final response. The
callback is purely additive, so the frozen list[str] trace contract is unchanged.
"""

from __future__ import annotations

from collections.abc import Callable


class Tracer:
    """Collects readable decision lines for one /advise run."""

    def __init__(self, on_append: Callable[[str], None] | None = None) -> None:
        self._lines: list[str] = []
        self._on_append = on_append

    def add(self, line: str) -> str:
        """Append a line and return it (so callers can also stream it).

        If an on_append callback was provided, it is invoked with the line so a
        live consumer (the SSE endpoint) sees it immediately.
        """
        self._lines.append(line)
        if self._on_append is not None:
            self._on_append(line)
        return line

    def step(self, actor: str, message: str) -> str:
        """Append a line attributed to an actor, e.g. '[Planner] ...'.

        Using a consistent '[Actor] message' shape makes the live trace read
        like a narrated decision log, which is exactly what we want to show the
        judges.
        """
        return self.add(f"[{actor}] {message}")

    @property
    def lines(self) -> list[str]:
        """The raw list, as required by the API/Trace contract."""
        return self._lines

"""
Router-switching check.

Stage 4 requirement: verify the Segment Router switches correctly between
Segment A (informal vendor) and Segment B (micro/small business).

Runs the real LLM router on both representative profiles and asserts each maps
to the expected segment. Run with:

    python -m app.check_router

Exits non-zero if either classification is wrong, so it doubles as a tiny
regression test we can re-run after any prompt change.
"""

from __future__ import annotations

import asyncio
import sys

from app.agents.segment_router import route_segment
from app.cli import _business_profile, _vendor_profile
from app.models import Segment
from app.trace import Tracer

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


async def _main() -> None:
    cases = [
        ("Segment A vendor", _vendor_profile(), Segment.INFORMAL_VENDOR),
        ("Segment B business", _business_profile(), Segment.MICRO_BUSINESS),
    ]

    all_ok = True
    for label, profile, expected in cases:
        tracer = Tracer()
        decision = await route_segment(profile, tracer)
        ok = decision.segment == expected
        all_ok = all_ok and ok
        status = "PASS" if ok else "FAIL"
        print(
            f"[{status}] {label}: got {decision.segment.value} "
            f"(expected {expected.value}, conf {decision.confidence:.2f})"
        )
        print(f"        reason: {decision.reasoning}")

    print("\nRouter switching:", "OK" if all_ok else "BROKEN")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    asyncio.run(_main())

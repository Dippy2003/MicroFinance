"use client";

import { useEffect, useRef } from "react";

// One colour per actor so the log reads like a multi-agent status feed
// (matching each actor's stage colour in StatusHeader's stepper).
const ACTOR_COLORS: Record<string, string> = {
  Planner: "#9aa1b0",
  Orchestrator: "#9aa1b0",
  SegmentRouter: "#ff7a30",
  EligibilityGate: "#ffb020",
  ProviderMatcher: "#34c759",
  DocPreparer: "#5ad1d6",
  DebtAdvisor: "#c39bff",
  Evaluator: "#ff5c8d",
};

function fmtElapsed(ms: number): string {
  const totalSec = Math.floor(ms / 1000);
  const m = Math.floor(totalSec / 60);
  const s = totalSec % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

/**
 * Renders the live trace lines verbatim (the frozen contract: the frontend
 * renders the strings as-is). We colour-code the "[Actor]" prefix per actor
 * and prefix each line with elapsed time since the run started, but never
 * alter the underlying text. Auto-scrolls to the newest line.
 */
export default function TracePanel({
  lines,
}: {
  lines: { text: string; elapsedMs: number }[];
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [lines]);

  return (
    <div className="trace" ref={ref}>
      {lines.length === 0 ? (
        <div className="trace-empty">
          The agent decision trace will stream here live.
        </div>
      ) : (
        lines.map(({ text, elapsedMs }, i) => {
          const m = text.match(/^(\[[^\]]+\])\s?(.*)$/);
          const actor = m?.[1]?.slice(1, -1);
          const color = actor ? ACTOR_COLORS[actor] : undefined;
          return (
            <div className="trace-line" key={i}>
              <span className="trace-time">{fmtElapsed(elapsedMs)}</span>{" "}
              {m ? (
                <>
                  <span className="actor" style={color ? { color } : undefined}>
                    {m[1]}
                  </span>{" "}
                  {m[2]}
                </>
              ) : (
                text
              )}
            </div>
          );
        })
      )}
    </div>
  );
}

"use client";

// Maps each backend actor tag to one of 5 pipeline stages, so the live trace
// can show a "Researching the web..."-style stepper instead of a raw log only.
const STAGES = [
  { label: "Routing", status: "Reading the borrower profile..." },
  { label: "Eligibility", status: "Checking eligibility..." },
  { label: "Matching", status: "Matching loan providers..." },
  { label: "Advising", status: "Preparing documents and debt advice..." },
  { label: "Evaluating", status: "Finalizing the verdict..." },
] as const;

const ACTOR_TO_STAGE: Record<string, number> = {
  Planner: 0,
  Orchestrator: 0,
  SegmentRouter: 0,
  EligibilityGate: 1,
  ProviderMatcher: 2,
  DocPreparer: 3,
  DebtAdvisor: 3,
  Evaluator: 4,
};

function currentStageIndex(lines: string[]): number {
  let stage = 0;
  for (const line of lines) {
    const m = line.match(/^\[([^\]]+)\]/);
    const actor = m?.[1];
    if (actor && actor in ACTOR_TO_STAGE) {
      stage = Math.max(stage, ACTOR_TO_STAGE[actor]);
    }
  }
  return stage;
}

export default function StatusHeader({
  lines,
  running,
  done,
}: {
  lines: string[];
  running: boolean;
  done: boolean;
}) {
  if (!running && !done) return null;

  const stageIndex = done ? STAGES.length - 1 : currentStageIndex(lines);
  const progressPct = done ? 100 : ((stageIndex + 0.5) / STAGES.length) * 100;

  return (
    <div className="status-header">
      <div className="status-row">
        <span className={`status-orb${running ? " spinning" : ""}`} />
        <span className="status-text">
          {done ? "Done" : STAGES[stageIndex].status}
        </span>
      </div>

      <div className="status-steps">
        {STAGES.map((s, i) => (
          <span
            key={s.label}
            className={`status-step${i < stageIndex || done ? " done" : ""}${
              i === stageIndex && !done ? " active" : ""
            }`}
          >
            <span className="status-step-dot" />
            {s.label}
          </span>
        ))}
      </div>

      <div className="status-bar">
        <div className="status-bar-fill" style={{ width: `${progressPct}%` }} />
      </div>
    </div>
  );
}

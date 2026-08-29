"use client";

import { useEffect, useRef, useState } from "react";
import { streamAdvice } from "@/lib/api";
import type { AdviceResponse, BorrowerProfile, Verdict } from "@/lib/types";
import MatchCard from "./components/MatchCard";
import TracePanel from "./components/TracePanel";
import StatusHeader from "./components/StatusHeader";
import { BorderBeamButton } from "@/components/ui/border-beam-button";
import { Button } from "@/components/ui/button";

// A sensible default profile (the Segment A vendor) so the demo runs in one click.
const DEFAULT_PROFILE: BorrowerProfile = {
  name: "Kamala Perera",
  age: 38,
  district: "Gampaha",
  occupation: "Vegetable vendor at the local market",
  monthly_income_lkr: 60000,
  monthly_expenses_lkr: 35000,
  existing_debt_lkr: 0,
  requested_amount_lkr: 150000,
  loan_purpose: "Buy stock in bulk and a second cart",
  has_bank_account: false,
  has_business_registration: false,
  months_in_operation: null,
  notes: "Sells daily at the pola; no formal registration.",
};

// The debt advice and document checklist are emitted into the trace (they are
// not separate fields on the frozen AdviceResponse). We extract them for display.
function extractDebtAdvice(trace: string[]): string | null {
  const line = [...trace].reverse().find((l) => l.startsWith("[DebtAdvisor]"));
  return line ? line.replace("[DebtAdvisor]", "").trim() : null;
}

// The Doc Preparer emits each document as a "[DocPreparer]   - <item>" line.
// We collect those (from the LAST DocPreparer run, in case of a re-query loop).
function extractDocuments(trace: string[]): string[] {
  const docs: string[] = [];
  for (const l of trace) {
    const m = l.match(/^\[DocPreparer\]\s+-\s+(.*)$/);
    if (m) docs.push(m[1].trim());
    // A new "Prepared N document(s)." line marks a fresh run; reset the list so
    // we keep only the most recent checklist.
    else if (/^\[DocPreparer\] Prepared \d+ required document/.test(l)) {
      docs.length = 0;
    }
  }
  return docs;
}

type TraceLine = { text: string; elapsedMs: number };

export default function Home() {
  const [profile, setProfile] = useState<BorrowerProfile>(DEFAULT_PROFILE);
  const [lines, setLines] = useState<TraceLine[]>([]);
  const [result, setResult] = useState<AdviceResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newIncome, setNewIncome] = useState<string>("");
  const esRef = useRef<EventSource | null>(null);
  // Wall-clock time the current run started, so trace lines can show elapsed
  // time (the backend trace itself carries no timestamps).
  const runStartRef = useRef<number>(0);
  const resultRef = useRef<HTMLDivElement | null>(null);

  // The result panel renders below the fold; scroll it into view as soon as
  // it appears so the user isn't left staring at the trace panel wondering
  // where the answer went.
  useEffect(() => {
    if (result) {
      resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [result]);

  function update<K extends keyof BorrowerProfile>(
    key: K,
    value: BorrowerProfile[K],
  ) {
    setProfile((p) => ({ ...p, [key]: value }));
  }

  // Parse a number input into number | null (empty -> null).
  function numOrNull(v: string): number | null {
    if (v.trim() === "") return null;
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  }

  function run(incomeChangeTo: number | null) {
    // Close any prior stream before starting a new one.
    esRef.current?.close();
    setRunning(true);
    setError(null);
    if (incomeChangeTo == null) {
      // Fresh run: clear previous output. On a re-query we KEEP the trace so the
      // before/after story is visible in one continuous log.
      setLines([]);
      setResult(null);
      runStartRef.current = Date.now();
    }

    esRef.current = streamAdvice(profile, incomeChangeTo, {
      onLine: (line) =>
        setLines((prev) => [
          ...prev,
          { text: line, elapsedMs: Date.now() - runStartRef.current },
        ]),
      onResult: (res) => setResult(res),
      onError: (msg) => {
        setError(msg);
        setRunning(false);
      },
      onDone: () => setRunning(false),
    });
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    run(null);
  }

  function onRequery() {
    const v = numOrNull(newIncome);
    if (v == null) {
      setError("Enter a valid new monthly income to re-query.");
      return;
    }
    // Reflect the new income in the form, then re-run with the change signal.
    update("monthly_income_lkr", v);
    run(v);
  }

  const verdict: Verdict | null = result?.verdict ?? null;
  const debtAdvice = result ? extractDebtAdvice(result.trace) : null;
  const documents = result ? extractDocuments(result.trace) : [];

  return (
    <div className="container">
      <div className="header">
        <h1>MicroLoan AI Agent</h1>
        <p>AI loan advisory for underbanked Sri Lanka (AgenTrix 2026)</p>
      </div>

      <div className="grid">
        {/* LEFT: profile form */}
        <form className="panel" onSubmit={onSubmit}>
          <h2>Borrower profile</h2>
          <fieldset className="profile-fields" disabled={running}>

          <label>Name</label>
          <input
            value={profile.name}
            onChange={(e) => update("name", e.target.value)}
            required
          />

          <label>Occupation</label>
          <input
            value={profile.occupation}
            onChange={(e) => update("occupation", e.target.value)}
            required
          />

          <div className="row">
            <div>
              <label>District</label>
              <input
                value={profile.district ?? ""}
                onChange={(e) => update("district", e.target.value)}
              />
            </div>
            <div>
              <label>Age</label>
              <input
                type="number"
                value={profile.age ?? ""}
                onChange={(e) => update("age", numOrNull(e.target.value))}
              />
            </div>
          </div>

          <div className="row">
            <div>
              <label>Monthly income (LKR)</label>
              <input
                type="number"
                value={profile.monthly_income_lkr ?? ""}
                onChange={(e) =>
                  update("monthly_income_lkr", numOrNull(e.target.value))
                }
              />
            </div>
            <div>
              <label>Monthly expenses (LKR)</label>
              <input
                type="number"
                value={profile.monthly_expenses_lkr ?? ""}
                onChange={(e) =>
                  update("monthly_expenses_lkr", numOrNull(e.target.value))
                }
              />
            </div>
          </div>

          <div className="row">
            <div>
              <label>Existing debt balance (LKR)</label>
              <input
                type="number"
                value={profile.existing_debt_lkr ?? ""}
                onChange={(e) =>
                  update("existing_debt_lkr", numOrNull(e.target.value))
                }
              />
            </div>
            <div>
              <label>Requested amount (LKR)</label>
              <input
                type="number"
                value={profile.requested_amount_lkr ?? ""}
                onChange={(e) =>
                  update("requested_amount_lkr", numOrNull(e.target.value))
                }
              />
            </div>
          </div>

          <label>Loan purpose</label>
          <input
            value={profile.loan_purpose ?? ""}
            onChange={(e) => update("loan_purpose", e.target.value)}
          />

          <div className="row">
            <div>
              <label>Months in operation</label>
              <input
                type="number"
                value={profile.months_in_operation ?? ""}
                onChange={(e) =>
                  update("months_in_operation", numOrNull(e.target.value))
                }
              />
            </div>
          </div>

          <div className="checks">
            <label>
              <input
                type="checkbox"
                checked={!!profile.has_bank_account}
                onChange={(e) => update("has_bank_account", e.target.checked)}
              />
              Has bank account
            </label>
            <label>
              <input
                type="checkbox"
                checked={!!profile.has_business_registration}
                onChange={(e) =>
                  update("has_business_registration", e.target.checked)
                }
              />
              Has business registration
            </label>
          </div>

          <label>Notes</label>
          <textarea
            value={profile.notes ?? ""}
            onChange={(e) => update("notes", e.target.value)}
          />
          </fieldset>

          <BorderBeamButton
            className="btn-primary"
            borderBeamClassName="w-full"
            type="submit"
            disabled={running}
            active={!running}
            beamSize="md"
          >
            {running ? "Running agents..." : "Get loan advice"}
          </BorderBeamButton>
          {error ? <div className="error">{error}</div> : null}
        </form>

        {/* RIGHT: live trace */}
        <div className="panel">
          <h2>Live agent trace</h2>
          <StatusHeader lines={lines.map((l) => l.text)} running={running} done={!!result} />
          <TracePanel lines={lines} />
        </div>
      </div>

      {/* RESULT */}
      {result ? (
        <div className="panel" style={{ marginTop: 20 }} ref={resultRef}>
          <h2>
            Result{" "}
            {verdict ? (
              <span className={`verdict ${verdict}`}>{verdict}</span>
            ) : null}
          </h2>

          {verdict === "escalate" ? (
            <p>
              We could not automatically place this borrower. The trace above
              explains why (for example, an unmet eligibility criterion).
            </p>
          ) : null}

          {result.matches.length > 0 ? (
            <>
              <h2 style={{ marginTop: 8 }}>Provider matches</h2>
              {result.matches.map((m, i) => (
                <MatchCard key={i} match={m} />
              ))}
            </>
          ) : null}

          {documents.length > 0 ? (
            <>
              <h2 style={{ marginTop: 16 }}>Document checklist</h2>
              <ul className="checklist">
                {documents.map((d, i) => (
                  <li key={i}>{d}</li>
                ))}
              </ul>
            </>
          ) : null}

          {debtAdvice ? (
            <>
              <h2 style={{ marginTop: 16 }}>Debt advice</h2>
              <p style={{ fontSize: 14 }}>{debtAdvice}</p>
            </>
          ) : null}

          {/* Income-change re-query interaction */}
          {verdict !== "escalate" ? (
            <div className="income-change">
              <h2>Income changed? Re-query</h2>
              <div className="row-inline">
                <div style={{ flex: 1 }}>
                  <label>New monthly income (LKR)</label>
                  <input
                    type="number"
                    placeholder="e.g. 200000"
                    value={newIncome}
                    onChange={(e) => setNewIncome(e.target.value)}
                  />
                </div>
                <Button
                  className="btn-secondary"
                  onClick={onRequery}
                  disabled={running}
                  type="button"
                >
                  Re-rank on new income
                </Button>
              </div>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

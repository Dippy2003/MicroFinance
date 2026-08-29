// TypeScript mirrors of the backend's FROZEN Pydantic contracts.
// Kept in sync by hand; if a backend model changes, change it here too.

export interface BorrowerProfile {
  name: string;
  age?: number | null;
  district?: string | null;
  occupation: string;
  monthly_income_lkr?: number | null;
  monthly_expenses_lkr?: number | null;
  existing_debt_lkr?: number | null;
  requested_amount_lkr?: number | null;
  loan_purpose?: string | null;
  has_bank_account?: boolean | null;
  has_business_registration?: boolean | null;
  months_in_operation?: number | null;
  notes?: string | null;
}

export interface ProviderMatch {
  provider_name: string;
  product_name?: string | null;
  score: number;
  rationale: string;
  indicative_terms?: string | null;
  source: string;
  // Additive comparison fields (backend Stage 4).
  interest_rate?: string | null;
  max_amount_lkr?: number | null;
  tenure?: string | null;
  key_requirement?: string | null;
  is_recommended: boolean;
}

export type Verdict = "done" | "loop" | "escalate";

export interface AdviceResponse {
  verdict: Verdict;
  matches: ProviderMatch[];
  trace: string[];
}

// Shapes of the SSE frames emitted by GET /advise/stream.
export type StreamFrame =
  | { line: string }
  | { result: AdviceResponse }
  | { done: true }
  | { error: string };

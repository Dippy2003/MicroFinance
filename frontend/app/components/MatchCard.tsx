import type { ProviderMatch } from "@/lib/types";
import { MinimalCard } from "@/components/ui/minimal-card";
import { Badge } from "@/components/ui/badge";

function fmtLkr(n?: number | null): string {
  if (n == null) return "n/a";
  return "LKR " + n.toLocaleString("en-US");
}

export default function MatchCard({ match }: { match: ProviderMatch }) {
  return (
    <MinimalCard
      className={`card${match.is_recommended ? " recommended" : ""} p-4!`}
    >
      <div className="card-head">
        <span className="name">
          {match.provider_name}
          {match.product_name ? ` - ${match.product_name}` : ""}
        </span>
        {match.is_recommended ? (
          <Badge className="bg-[#34c759] text-[#052b12] uppercase">
            Recommended
          </Badge>
        ) : (
          <Badge variant="secondary" className="text-(--text-muted)">
            score {match.score.toFixed(2)}
          </Badge>
        )}
      </div>

      <dl className="terms">
        <dt>Interest</dt>
        <dd>{match.interest_rate ?? "n/a"}</dd>
        <dt>Max amount</dt>
        <dd>{fmtLkr(match.max_amount_lkr)}</dd>
        <dt>Tenure</dt>
        <dd>{match.tenure ?? "n/a"}</dd>
        <dt>Key requirement</dt>
        <dd>{match.key_requirement ?? "n/a"}</dd>
      </dl>

      <div className="rationale">{match.rationale}</div>
      <div className="source">Source: {match.source}</div>
    </MinimalCard>
  );
}

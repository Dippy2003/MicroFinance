"""
Terminal entry point for running the orchestrator end-to-end.

Stage 2 requirement: run Segment A end-to-end in the terminal on stub data and
watch the trace print. Run with:

    python -m app.cli                # default informal-vendor profile (Segment A)
    python -m app.cli --ineligible   # a profile that fails the gate (ESCALATE)

This calls the SAME run_pipeline the API will use, so the terminal and the API
exercise identical orchestration logic.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.models import BorrowerProfile
from app.orchestrator.runner import run_pipeline

# On Windows the default console codepage (cp1252) can't encode some Unicode the
# LLM emits (e.g. non-breaking hyphen). Force UTF-8 on our streams so the CLI
# never crashes just printing the trace. errors="replace" is a final safety net.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _vendor_profile() -> BorrowerProfile:
    """A representative Segment A (informal vendor) borrower."""
    return BorrowerProfile(
        name="Kamala Perera",
        age=38,
        district="Gampaha",
        occupation="Vegetable vendor at the local market",
        monthly_income_lkr=60_000,
        monthly_expenses_lkr=35_000,
        existing_debt_lkr=0,
        requested_amount_lkr=150_000,
        loan_purpose="Buy stock in bulk and a second cart",
        has_bank_account=False,
        has_business_registration=False,
        notes="Sells daily at the pola; no formal registration.",
    )


def _business_profile() -> BorrowerProfile:
    """A representative Segment B (micro/small business) borrower.

    Registered business with operating history and a bank account -> the router
    should classify this as micro_business and route to bank/finance SME loans.
    """
    return BorrowerProfile(
        name="Nuwan Fernando",
        age=41,
        district="Colombo",
        occupation="Owner of a small furniture workshop and retail shop",
        monthly_income_lkr=350_000,
        monthly_expenses_lkr=220_000,
        existing_debt_lkr=100_000,
        requested_amount_lkr=800_000,
        loan_purpose="Buy machinery and expand the workshop",
        has_bank_account=True,
        has_business_registration=True,
        months_in_operation=30,
        notes="Registered business (BR) operating ~2.5 years; keeps bank statements.",
    )


def _ineligible_profile() -> BorrowerProfile:
    """A profile that should fail the placeholder eligibility gate."""
    p = _vendor_profile()
    p.monthly_income_lkr = 5_000          # tiny income
    p.requested_amount_lkr = 500_000      # vs large ask -> fails affordability
    return p


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Run the MicroLoan orchestrator.")
    parser.add_argument(
        "--business",
        action="store_true",
        help="Use a Segment B (micro/small business) profile.",
    )
    parser.add_argument(
        "--ineligible",
        action="store_true",
        help="Use a profile that fails the eligibility gate (expects ESCALATE).",
    )
    parser.add_argument(
        "--income-change-to",
        type=float,
        default=None,
        metavar="LKR",
        help="Trigger the re-query loop: after the first result, change monthly "
        "income to this value and re-rank (expects a LOOP then DONE in the trace).",
    )
    args = parser.parse_args()

    if args.ineligible:
        profile = _ineligible_profile()
    elif args.business:
        profile = _business_profile()
    else:
        profile = _vendor_profile()

    response = await run_pipeline(profile, income_change_to=args.income_change_to)

    print("\n================ LIVE TRACE ================")
    for line in response.trace:
        print(line)

    print("\n================ RESULT ====================")
    print(f"Verdict: {response.verdict.value}")
    print(f"Matches: {len(response.matches)}  (★ = recommended)\n")
    for m in response.matches:
        star = "★ " if m.is_recommended else "  "
        print(f"{star}{m.provider_name}  (score {m.score})")
        print(f"    interest : {m.interest_rate or 'n/a'}")
        print(
            f"    max LKR  : {f'{m.max_amount_lkr:,.0f}' if m.max_amount_lkr else 'n/a'}"
        )
        print(f"    tenure   : {m.tenure or 'n/a'}")
        print(f"    needs    : {m.key_requirement or 'n/a'}")
        print(f"    why      : {m.rationale}")
        print(f"    source   : {m.source}\n")


if __name__ == "__main__":
    asyncio.run(_main())

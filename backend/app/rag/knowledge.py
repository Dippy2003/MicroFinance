"""
The RAG knowledge base: real, sourced Sri Lankan provider/regulation facts
(researched June 2026).

This is the SINGLE source of truth for the document corpus. Two consumers use it:
  1. scripts/ingest.py embeds these chunks into Supabase pgvector (Stage 6).
  2. rag/retriever.py uses them as an automatic keyword fallback when Supabase
     is not configured, so the app still runs end to end offline.

Each chunk carries a `source` citation so every downstream match is defensible.
Figures (amounts, rates) are indicative and attributed to the issuer.
"""

from __future__ import annotations

from app.models import Chunk

# Knowledge keyed by segment string (matches Segment enum values).
KNOWLEDGE: dict[str, list[Chunk]] = {
    "informal_vendor": [
        Chunk(
            text=(
                "Regulation: Licensed Microfinance Companies and Licensed "
                "Finance Companies in Sri Lanka are capped by the Central Bank "
                "(CBSL) on microfinance lending. The all-in rate (interest plus "
                "all charges) may not exceed 35% per annum. Informal vendors "
                "should compare the all-in rate, not just the headline interest."
            ),
            source="CBSL: Maximum Rate of Interest on Microfinance Loans (Direction)",
        ),
        Chunk(
            text=(
                "Provider: LOLC Finance PLC (Micro Loans). Largest personal-"
                "finance provider in the NBFI sector. Loan cycle from "
                "LKR 15,000 up to LKR 300,000, repaid over 12-24 months in "
                "monthly instalments. Suited to micro-entrepreneurs and informal "
                "vendors needing working capital with fast approval."
            ),
            source="lolcfinance.com/loans-and-leasing/micro-loans (2026)",
        ),
        Chunk(
            text=(
                "Provider: Berendina Micro Investments Co. Ltd (BMIC). Sri "
                "Lanka's first licensed Microfinance Company under the "
                "Microfinance Act No. 6 of 2016. Targets low-income micro-"
                "entrepreneurs; offers credit at competitive rates versus other "
                "NGO/private microfinance institutions. Group guarantee or "
                "guarantor common; no formal collateral for small first cycles."
            ),
            source="microfinance.lk: Berendina Micro Investments (2026)",
        ),
        Chunk(
            text=(
                "Provider: People's Bank People's Power Loan Scheme. For MSMEs "
                "with annual turnover under LKR 25 million. Loan up to LKR 5 "
                "million; interest 10-12.5% p.a. (fixed, tiered by amount); "
                "repayment 3-5 years with grace periods; secured by guarantees "
                "or property mortgage. Good step-up option for a growing vendor."
            ),
            source="peoplesbank.lk/micro-finance-loans (2026)",
        ),
        Chunk(
            text=(
                "Provider: People's Bank Vanitha Saviya Loan Scheme. For women "
                "entrepreneurs aged 25-65 in feasible income-generating "
                "activities. Loan up to LKR 25 million; interest 8-12.5% p.a. "
                "(fixed, tiered); repayment 3-5 years; secured by two personal "
                "guarantees or an immovable-property mortgage."
            ),
            source="peoplesbank.lk/micro-finance-loans (2026)",
        ),
        Chunk(
            text=(
                "Eligibility norm for informal-vendor microloans: applicant "
                "typically must show an existing income-generating activity, a "
                "valid NIC, and residence in the operating area. A formal bank "
                "account is often NOT required for first-cycle microfinance, "
                "unlike bank SME loans."
            ),
            source="CBSL microfinance sector overview (2026)",
        ),
    ],
    "micro_business": [
        Chunk(
            text=(
                "Provider: People's Bank SMED Scheme (Small and Medium "
                "Enterprises Development). For registered businesses with annual "
                "turnover LKR 20-1,000 million across agriculture, industry, "
                "trading, IT, apparel, tourism, construction. Loan on need basis; "
                "interest AWPLR + 2.5% p.a. (monthly review, no floor rate); "
                "repayment up to 10 years incl. up to 24-month grace period."
            ),
            source="peoplesbank.lk/sme-loans (2026)",
        ),
        Chunk(
            text=(
                "Provider: People's Bank Business Power Loan. Up to LKR 250 "
                "million (investment) / LKR 50 million (working capital). "
                "Interest 11% p.a. fixed for years 1-3, then weekly AWPLR + 2.0%. "
                "Repayment 10 years investment / 3 years working capital. "
                "Eligible sectors: agriculture, manufacturing, food/beverage, "
                "essential services, construction (no pure trading)."
            ),
            source="peoplesbank.lk/sme-loans (2026)",
        ),
        Chunk(
            text=(
                "Provider: People's Bank PEOPLE'S SPARK Loan. For citizens "
                "aged 20-45 with O/A Levels, not in default. Max LKR 2.5 million; "
                "interest 7% fixed (up to LKR 500K), 10% fixed (up to LKR 1M), or "
                "AWPLR + 2% above LKR 1M; repayment 7 yrs investment / 3 yrs "
                "working capital. Strong fit for a young first-time business owner."
            ),
            source="peoplesbank.lk/sme-loans (2026)",
        ),
        Chunk(
            text=(
                "Provider: Bank of Ceylon (BOC) Development Banking. MSME "
                "schemes including SME Energizer, SME Circle, BOC Youth (young "
                "entrepreneurs) and BOC e-Creator (digital creators). Term and "
                "working-capital facilities for registered small businesses; "
                "exact amounts/terms are set per scheme on application."
            ),
            source="boc.lk/business-banking/development-banking (2026)",
        ),
        Chunk(
            text=(
                "Provider: Commercial Bank of Ceylon (ComBank). Ranked the "
                "largest lender to SMEs in Sri Lanka for five consecutive years "
                "(2020-2024); disbursed over LKR 14 billion across ~11,869 MSME "
                "loans (Jan 2025-Mar 2026). Backed by an IFC risk-sharing "
                "facility covering 50% of principal losses on eligible SME loans, "
                "with a focus on women-owned and agri-businesses."
            ),
            source="dailymirror.lk: ComBank MSME lending; ifc.org (2025-2026)",
        ),
        Chunk(
            text=(
                "Eligibility norm for micro-business bank loans: valid business "
                "registration (BR / Certificate of Incorporation), typically "
                "6-12 months in operation, a business bank account with "
                "statements, and demonstrable repayment capacity (income "
                "comfortably exceeding expenses plus existing debt service). "
                "Note: VAT registration is required once turnover exceeds "
                "LKR 9 million per quarter (threshold lowered April 2026)."
            ),
            source="br.lk + simplebooks.com SL business registration guides (2026)",
        ),
    ],
}


def all_chunks() -> list[tuple[str, Chunk]]:
    """Flatten the knowledge base into (segment, chunk) pairs for ingestion."""
    return [(segment, chunk) for segment, chunks in KNOWLEDGE.items() for chunk in chunks]

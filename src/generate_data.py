"""Generate a synthetic retail/SME loan book with monthly performance snapshots.

The data is fake but behaves like a real portfolio: riskier grades roll into
arrears more often, older vintages season, and a handful of records are
deliberately broken so the data-quality step has something to catch.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

GRADES = ["A", "B", "C", "D", "E"]
PRODUCTS = {"Personal Loan": (50_000, 800_000, 12, 60),
            "Auto Loan": (300_000, 1_500_000, 24, 84),
            "SME Term Loan": (500_000, 5_000_000, 12, 60),
            "Home Loan": (1_500_000, 9_000_000, 120, 240)}
REGIONS = ["North", "South", "East", "West", "Central"]
BUCKETS = ["Current", "1-30 DPD", "31-60 DPD", "61-90 DPD", "90+ DPD"]

# Monthly chance a Current loan misses a payment, by grade.
ENTRY = {"A": 0.006, "B": 0.012, "C": 0.022, "D": 0.038, "E": 0.06}
# Once in arrears: chance of rolling one bucket worse vs paying back to Current.
ROLL_FWD = {"A": 0.22, "B": 0.28, "C": 0.36, "D": 0.45, "E": 0.55}
CURE = 0.40
PRODUCT_RISK = {"Personal Loan": 1.25, "Auto Loan": 0.9, "SME Term Loan": 1.35, "Home Loan": 0.6}
BASE_RATE = {"A": 9.5, "B": 11.0, "C": 13.5, "D": 16.0, "E": 19.5}


def make_loans(n: int, rng: np.random.Generator) -> pd.DataFrame:
    products = rng.choice(list(PRODUCTS), size=n, p=[0.4, 0.25, 0.2, 0.15])
    grades = rng.choice(GRADES, size=n, p=[0.25, 0.3, 0.25, 0.13, 0.07])
    orig = pd.to_datetime("2023-01-01") + pd.to_timedelta(rng.integers(0, 1095, n), unit="D")
    rows = []
    for i, (prod, g, od) in enumerate(zip(products, grades, orig)):
        lo, hi, tmin, tmax = PRODUCTS[prod]
        amt = round(float(rng.uniform(lo, hi)), -3)
        term = int(rng.choice(range(tmin, tmax + 1, 12)))
        rows.append({
            "loan_id": f"LN{100000 + i}",
            "customer_id": f"CU{rng.integers(10000, 99999)}",
            "product": prod,
            "grade": g,
            "region": rng.choice(REGIONS),
            "origination_date": od.date(),
            "original_amount": amt,
            "interest_rate": round(BASE_RATE[g] + rng.normal(0, 0.6), 2),
            "term_months": term,
            "ltv_pct": round(float(rng.uniform(45, 90)), 1) if prod in ("Home Loan", "Auto Loan") else None,
        })
    return pd.DataFrame(rows)


def make_performance(loans: pd.DataFrame, months: pd.DatetimeIndex, rng: np.random.Generator) -> pd.DataFrame:
    out = []
    for loan in loans.itertuples(index=False):
        od = pd.Timestamp(loan.origination_date)
        bucket, bal, months_npa = 0, loan.original_amount, 0
        r = loan.interest_rate / 1200
        emi = bal * r / (1 - (1 + r) ** -loan.term_months)
        for m in months:
            if m < od.to_period("M").to_timestamp() + pd.offsets.MonthBegin(1):
                continue
            if bal <= 0:
                break
            u = rng.random()
            if bucket == 0:
                if u < ENTRY[loan.grade] * PRODUCT_RISK[loan.product]:
                    bucket = 1
            elif bucket < 4:
                if u < CURE:
                    bucket = 0
                elif u < CURE + ROLL_FWD[loan.grade]:
                    bucket += 1
            if bucket == 4:
                months_npa += 1
                if months_npa > 6:  # written off after six months at 90+ DPD
                    break
            paid = emi if bucket == 0 else 0.0
            principal = max(paid - bal * r, 0)
            bal = max(bal - principal, 0)
            out.append({
                "snapshot_month": m.date(),
                "loan_id": loan.loan_id,
                "outstanding_balance": round(bal, 2),
                "dpd_bucket": BUCKETS[bucket],
                "days_past_due": [0, 15, 45, 75, 120][bucket] + int(rng.integers(0, 10)) * (bucket > 0),
                "payment_amount": round(paid, 2),
            })
    return pd.DataFrame(out)


def inject_issues(loans: pd.DataFrame, perf: pd.DataFrame, rng: np.random.Generator):
    """Break a few records on purpose so the DQ checks have real work to do."""
    loans = loans.copy(); perf = perf.copy()
    idx = rng.choice(loans.index, 25, replace=False)
    loans.loc[idx[:10], "grade"] = None                      # missing grade
    loans.loc[idx[10:18], "interest_rate"] = -1.0            # impossible rate
    loans = pd.concat([loans, loans.loc[idx[18:25]]])        # duplicate loans
    pidx = rng.choice(perf.index, 40, replace=False)
    perf.loc[pidx[:15], "outstanding_balance"] *= -1         # negative balance
    orphans = perf.loc[pidx[15:40]].copy(); orphans["loan_id"] = "LN999999"
    perf = pd.concat([perf, orphans])                        # loan not in master
    return loans.reset_index(drop=True), perf.reset_index(drop=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--loans", type=int, default=12_000)
    ap.add_argument("--out", type=Path, default=Path("data/raw"))
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    months = pd.date_range("2024-01-01", "2025-12-01", freq="MS")
    loans = make_loans(a.loans, rng)
    perf = make_performance(loans, months, rng)
    loans, perf = inject_issues(loans, perf, rng)
    a.out.mkdir(parents=True, exist_ok=True)
    loans.to_csv(a.out / "loans.csv", index=False)
    perf.to_csv(a.out / "loan_performance.csv", index=False)
    print(f"loans: {len(loans):,}  performance rows: {len(perf):,}")


if __name__ == "__main__":
    main()

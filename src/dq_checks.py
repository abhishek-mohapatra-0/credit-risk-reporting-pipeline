"""Data-quality checks run before anything reaches the risk report.

Each check returns how many rows failed. Failing rows are moved to a
quarantine file instead of being silently dropped, so someone can follow up.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

VALID_GRADES = {"A", "B", "C", "D", "E"}
VALID_BUCKETS = {"Current", "1-30 DPD", "31-60 DPD", "61-90 DPD", "90+ DPD"}


@dataclass
class CheckResult:
    table: str
    check: str
    failed_rows: int
    total_rows: int
    severity: str

    @property
    def status(self) -> str:
        return "PASS" if self.failed_rows == 0 else ("FAIL" if self.severity == "critical" else "WARN")


def check_loans(loans: pd.DataFrame) -> tuple[pd.DataFrame, list[CheckResult], pd.DataFrame]:
    n = len(loans)
    rules = {
        "duplicate loan_id": (loans.duplicated("loan_id", keep="first"), "critical"),
        "missing grade": (loans["grade"].isna(), "critical"),
        "grade outside A-E": (loans["grade"].notna() & ~loans["grade"].isin(VALID_GRADES), "critical"),
        "interest rate not in 0-40%": (~loans["interest_rate"].between(0, 40), "critical"),
        "non-positive original amount": (loans["original_amount"] <= 0, "critical"),
        "LTV above 100% (review)": (loans["ltv_pct"].fillna(0) > 100, "warning"),
    }
    return _apply(loans, "loans", rules, n)


def check_performance(perf: pd.DataFrame, valid_loans: pd.Series) -> tuple[pd.DataFrame, list[CheckResult], pd.DataFrame]:
    n = len(perf)
    rules = {
        "loan_id not in loan master": (~perf["loan_id"].isin(valid_loans), "critical"),
        "negative outstanding balance": (perf["outstanding_balance"] < 0, "critical"),
        "unknown DPD bucket": (~perf["dpd_bucket"].isin(VALID_BUCKETS), "critical"),
        "duplicate loan-month": (perf.duplicated(["loan_id", "snapshot_month"], keep="first"), "critical"),
        "DPD > 0 but bucket Current": ((perf["days_past_due"] > 0) & (perf["dpd_bucket"] == "Current"), "warning"),
    }
    return _apply(perf, "loan_performance", rules, n)


def _apply(df, table, rules, n):
    results, bad = [], pd.Series(False, index=df.index)
    reasons = pd.Series("", index=df.index)
    for name, (mask, sev) in rules.items():
        mask = mask.fillna(False)
        results.append(CheckResult(table, name, int(mask.sum()), n, sev))
        if sev == "critical":
            bad |= mask
            reasons = reasons.where(~mask, reasons + name + "; ")
    quarantine = df[bad].assign(dq_reason=reasons[bad].str.rstrip("; "))
    return df[~bad].copy(), results, quarantine


def run(raw: Path, clean: Path) -> pd.DataFrame:
    loans = pd.read_csv(raw / "loans.csv", parse_dates=["origination_date"])
    perf = pd.read_csv(raw / "loan_performance.csv", parse_dates=["snapshot_month"])
    loans_ok, r1, q1 = check_loans(loans)
    perf_ok, r2, q2 = check_performance(perf, loans_ok["loan_id"])
    clean.mkdir(parents=True, exist_ok=True)
    loans_ok.to_parquet(clean / "loans.parquet", index=False)
    perf_ok.to_parquet(clean / "loan_performance.parquet", index=False)
    pd.concat([q1.assign(source="loans"), q2.assign(source="loan_performance")]).to_csv(clean / "quarantine.csv", index=False)
    summary = pd.DataFrame([{**r.__dict__, "status": r.status} for r in r1 + r2])
    summary.to_csv(clean / "dq_summary.csv", index=False)
    return summary


if __name__ == "__main__":
    print(run(Path("data/raw"), Path("data/clean")).to_string(index=False))

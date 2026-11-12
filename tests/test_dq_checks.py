import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dq_checks import check_loans, check_performance  # noqa: E402


def _loans():
    return pd.DataFrame({
        "loan_id": ["L1", "L2", "L2", "L3"],
        "grade": ["A", None, None, "Z"],
        "interest_rate": [10.0, 12.0, 12.0, -1.0],
        "original_amount": [100.0, 200.0, 200.0, 300.0],
        "ltv_pct": [None, 80.0, 80.0, 120.0],
    })


def test_bad_loans_are_quarantined_not_dropped():
    clean, results, quarantine = check_loans(_loans())
    assert list(clean.loan_id) == ["L1"]
    assert len(quarantine) == 3
    assert "missing grade" in quarantine.iloc[0].dq_reason


def test_warning_does_not_quarantine():
    df = _loans().iloc[[0]].assign(ltv_pct=150.0)
    clean, results, _ = check_loans(df)
    assert len(clean) == 1
    assert {r.check: r.status for r in results}["LTV above 100% (review)"] == "WARN"


def test_performance_orphans_and_negatives():
    perf = pd.DataFrame({
        "loan_id": ["L1", "L9", "L1"],
        "snapshot_month": ["2025-01-01", "2025-01-01", "2025-02-01"],
        "outstanding_balance": [50.0, 10.0, -5.0],
        "dpd_bucket": ["Current", "Current", "Current"],
        "days_past_due": [0, 0, 0],
    })
    clean, results, q = check_performance(perf, pd.Series(["L1"]))
    assert len(clean) == 1
    assert set(q.loan_id) == {"L9", "L1"}

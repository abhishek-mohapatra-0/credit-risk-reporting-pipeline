-- Month-on-month roll rates: share of balance moving from one bucket to another.
WITH pairs AS (
    SELECT
        cur.snapshot_month,
        prev.dpd_bucket AS from_bucket,
        cur.dpd_bucket  AS to_bucket,
        prev.outstanding_balance AS bal
    FROM loan_performance cur
    JOIN loan_performance prev
      ON prev.loan_id = cur.loan_id
     AND prev.snapshot_month = cur.snapshot_month - INTERVAL '1' MONTH
)
SELECT
    from_bucket,
    to_bucket,
    ROUND(SUM(bal) / SUM(SUM(bal)) OVER (PARTITION BY from_bucket) * 100, 2) AS roll_pct
FROM pairs
WHERE snapshot_month >= DATE '2025-07-01'
GROUP BY from_bucket, to_bucket
ORDER BY from_bucket, to_bucket;

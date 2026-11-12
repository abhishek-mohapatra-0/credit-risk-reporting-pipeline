-- Latest-month balance split by days-past-due bucket and grade.
WITH latest AS (SELECT MAX(snapshot_month) AS m FROM loan_performance)
SELECT
    l.grade,
    p.dpd_bucket,
    COUNT(*)                                     AS accounts,
    ROUND(SUM(p.outstanding_balance) / 1e7, 2)   AS exposure_cr
FROM loan_performance p
JOIN loans l  ON l.loan_id = p.loan_id
JOIN latest x ON p.snapshot_month = x.m
WHERE p.outstanding_balance > 0
GROUP BY l.grade, p.dpd_bucket
ORDER BY l.grade, p.dpd_bucket;

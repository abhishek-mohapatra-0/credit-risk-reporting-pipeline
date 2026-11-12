-- Monthly portfolio snapshot: exposure, accounts and arrears by product.
SELECT
    p.snapshot_month,
    l.product,
    COUNT(*)                                                       AS active_accounts,
    ROUND(SUM(p.outstanding_balance) / 1e7, 2)                     AS exposure_cr,
    ROUND(SUM(CASE WHEN p.dpd_bucket <> 'Current' THEN p.outstanding_balance ELSE 0 END)
          / NULLIF(SUM(p.outstanding_balance), 0) * 100, 2)        AS arrears_pct,
    ROUND(SUM(CASE WHEN p.dpd_bucket = '90+ DPD' THEN p.outstanding_balance ELSE 0 END)
          / NULLIF(SUM(p.outstanding_balance), 0) * 100, 2)        AS npa_pct
FROM loan_performance p
JOIN loans l ON l.loan_id = p.loan_id
WHERE p.outstanding_balance > 0
GROUP BY p.snapshot_month, l.product
ORDER BY p.snapshot_month, l.product;

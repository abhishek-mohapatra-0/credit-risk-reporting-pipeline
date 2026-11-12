-- Concentration: latest exposure by region and product, with share of total.
WITH latest AS (SELECT MAX(snapshot_month) AS m FROM loan_performance),
book AS (
    SELECT l.region, l.product, p.outstanding_balance AS bal
    FROM loan_performance p
    JOIN loans l  ON l.loan_id = p.loan_id
    JOIN latest x ON p.snapshot_month = x.m
)
SELECT
    region,
    product,
    ROUND(SUM(bal) / 1e7, 2)                              AS exposure_cr,
    ROUND(SUM(bal) / SUM(SUM(bal)) OVER () * 100, 2)      AS share_pct
FROM book
GROUP BY region, product
ORDER BY exposure_cr DESC;

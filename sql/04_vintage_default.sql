-- Vintage analysis: cumulative % of loans that ever hit 90+ DPD, by origination quarter and grade.
WITH ever_default AS (
    SELECT loan_id, MAX(CASE WHEN dpd_bucket = '90+ DPD' THEN 1 ELSE 0 END) AS defaulted
    FROM loan_performance
    GROUP BY loan_id
)
SELECT
    CAST(YEAR(l.origination_date) AS VARCHAR) || '-Q' || CAST(QUARTER(l.origination_date) AS VARCHAR) AS vintage,
    l.grade,
    COUNT(*)                                  AS loans,
    ROUND(AVG(e.defaulted) * 100, 2)          AS default_rate_pct
FROM loans l
JOIN ever_default e ON e.loan_id = l.loan_id
GROUP BY 1, 2
ORDER BY 1, 2;

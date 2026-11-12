# Building the QuickSight dashboard

QuickSight has a 30-day free trial. Once `aws/setup.sh` has run:

1. In QuickSight, go to **Datasets → New dataset → Athena**, choose the `credit_risk` database.
2. Pick **Use custom SQL** and paste a query from `sql/` (start with `01_portfolio_summary.sql`).
   Prefix table names with `credit_risk.` Save it as **SPICE** so the dashboard is fast.
3. Repeat for `02_delinquency_buckets.sql` and `04_vintage_default.sql`.
4. Build one sheet with:
   - KPI tiles: exposure (cr), arrears %, NPA % for the latest month
   - Line chart: NPA % by month, colour by product
   - Stacked bar: exposure by grade split by DPD bucket
   - Heat map: vintage × grade default rate
5. Add a **snapshot_month** filter control and publish.

No AWS account? The CSVs in `reports/extracts/` load straight into Power BI or Tableau with the same visuals.

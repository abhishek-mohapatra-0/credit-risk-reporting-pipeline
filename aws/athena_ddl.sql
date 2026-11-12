-- Run in Athena after aws/setup.sh has uploaded the clean parquet files.
-- Replace <your-bucket> with the bucket name you used in setup.sh.

CREATE DATABASE IF NOT EXISTS credit_risk;

CREATE EXTERNAL TABLE IF NOT EXISTS credit_risk.loans (
    loan_id          string,
    customer_id      string,
    product          string,
    grade            string,
    region           string,
    origination_date timestamp,
    original_amount  double,
    interest_rate    double,
    term_months      bigint,
    ltv_pct          double
)
STORED AS PARQUET
LOCATION 's3://<your-bucket>/credit-risk/clean/loans/';

CREATE EXTERNAL TABLE IF NOT EXISTS credit_risk.loan_performance (
    snapshot_month      timestamp,
    loan_id             string,
    outstanding_balance double,
    dpd_bucket          string,
    days_past_due       bigint,
    payment_amount      double
)
STORED AS PARQUET
LOCATION 's3://<your-bucket>/credit-risk/clean/loan_performance/';

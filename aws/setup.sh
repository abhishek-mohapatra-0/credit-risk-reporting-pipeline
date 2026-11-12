#!/usr/bin/env bash
# Push the clean data to S3 and register it in Athena.
# Needs: AWS CLI v2 configured (aws configure) on a free-tier account.
# Usage: ./aws/setup.sh my-unique-bucket-name ap-south-1
set -euo pipefail

BUCKET="${1:?bucket name required}"
REGION="${2:-ap-south-1}"
PREFIX="s3://${BUCKET}/credit-risk"

aws s3 mb "s3://${BUCKET}" --region "${REGION}" 2>/dev/null || true
aws s3 cp data/clean/loans.parquet            "${PREFIX}/clean/loans/loans.parquet"
aws s3 cp data/clean/loan_performance.parquet "${PREFIX}/clean/loan_performance/loan_performance.parquet"

sed "s/<your-bucket>/${BUCKET}/g" aws/athena_ddl.sql > /tmp/athena_ddl.sql
# Athena runs one statement per call, so split on ';'
awk 'BEGIN{RS=";"} NF{print > "/tmp/stmt_" NR ".sql"}' /tmp/athena_ddl.sql
for f in /tmp/stmt_*.sql; do
  aws athena start-query-execution \
    --region "${REGION}" \
    --query-string "$(cat "$f")" \
    --result-configuration "OutputLocation=${PREFIX}/athena-results/" >/dev/null
done
rm -f /tmp/stmt_*.sql
echo "Tables created in Athena database 'credit_risk'. The queries in sql/ run there unchanged (prefix tables with credit_risk.)."

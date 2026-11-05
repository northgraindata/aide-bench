# Revenue monitor

The monitor compares `daily_revenue.revenue` with the average of the previous 7 days.
It alerts when the value is more than 10% lower.
The ingestion DAG `ingest_orders` runs at 02:00 UTC and `dbt_build` at 04:00 UTC.

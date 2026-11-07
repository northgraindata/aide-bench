# Orders stream ingestion

Orders reach `raw.orders_stream` through a Pub/Sub BigQuery subscription.
Delivery is at-least-once and not instant: the 99th percentile delay between `event_ts` and `ingested_ts` is 38 minutes during evening peaks, the median is 10 seconds.
A table is only complete for a day about 45 minutes after midnight.

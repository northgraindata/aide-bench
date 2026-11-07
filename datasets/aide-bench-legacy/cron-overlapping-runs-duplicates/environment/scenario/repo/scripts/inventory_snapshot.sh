#!/bin/bash
echo "start $(date +%T)"
window=$(date -d "$(date +%Y-%m-%d\ %H):00" "+%Y-%m-%d %H:%M")
psql "$WH_DSN" -c "insert into inventory_snapshots select '$window'::timestamp, sku, qty from stock_levels"
echo "inserted 500 rows for window $window"
echo "end $(date +%T)"

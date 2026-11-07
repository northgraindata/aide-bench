#!/bin/bash
out=/srv/export/crm_$(date +%Y%m%d).csv.gz
psql "$CRM_DSN" -c "\copy (select * from crm.contacts) to stdout csv header" | gzip > "$out"
echo "exported $out"

SET hive.exec.dynamic.partition=true;
SET hive.exec.dynamic.partition.mode=nonstrict;

-- staging_sales holds the files that arrived since the last archive step
INSERT OVERWRITE TABLE sales_daily PARTITION (dt)
SELECT order_id, dt
FROM staging_sales
WHERE dt >= '${hivevar:since}';

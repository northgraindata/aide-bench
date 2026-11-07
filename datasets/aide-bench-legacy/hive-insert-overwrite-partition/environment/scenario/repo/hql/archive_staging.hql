-- runs at 05:30, before the load: moves fully processed days out of staging
INSERT OVERWRITE TABLE sales_archive PARTITION (dt)
SELECT order_id, dt FROM staging_sales WHERE dt < current_date;
TRUNCATE TABLE staging_sales;

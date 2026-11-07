create or replace table reporting.customer_ltv as
select
  c.cust_id,
  c.region,
  sum(o.amount) as ltv
from crm.customers c
join sales.orders o on o.customer_id = c.cust_id
group by 1, 2

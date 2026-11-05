select order_date, sum(amount) as revenue
from fct_orders_enriched
group by 1

select o.order_id, o.order_date, o.customer_id, c.name, o.amount
from orders_fact o
join dim_customer c on o.customer_id = c.customer_id

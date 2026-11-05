select order_id, order_date, currency, amount
from raw_orders
where currency is not null

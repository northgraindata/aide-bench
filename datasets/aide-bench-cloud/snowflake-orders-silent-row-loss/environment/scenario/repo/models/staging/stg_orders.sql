select *
from {{ source('raw', 'orders_raw') }}
where currency is not null

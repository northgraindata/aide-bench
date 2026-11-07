{{ config(materialized='table') }}

select segment, sum(amount) as revenue
from {{ ref('orders') }}
group by 1

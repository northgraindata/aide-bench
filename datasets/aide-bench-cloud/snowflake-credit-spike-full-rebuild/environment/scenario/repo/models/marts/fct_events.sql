{{ config(materialized='table') }}

select e.event_id, e.user_id, e.event_ts, u.segment
from {{ source('raw', 'events') }} e
join {{ ref('dim_users') }} u on e.user_id = u.user_id

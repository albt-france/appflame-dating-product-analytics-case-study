-- 07 Re-engagement pushes by local send hour: open rate and same-day return, with a 95% margin of error.
-- The scheduler assigns the hour from a hash of user_id, so hours are close to randomly assigned:
-- differences between hours can be read as causal (a natural experiment), not just a correlation.
-- ClickHouse equivalent: avg(opened) ... GROUP BY toHour(sent_at_local).
select local_hour,
       count(*)                                                                     as pushes,
       round(avg(opened::int), 4)                                                   as open_rate,
       round(avg(returned_same_day::int), 4)                                        as return_rate,
       round(1.96 * sqrt(avg(opened::int) * (1 - avg(opened::int)) / count(*)), 4) as open_rate_moe95
from notifications
group by local_hour
order by local_hour;

-- 08 Acquisition channels (May-Jul cohorts, >= 90 days of history): cost per sign-up, day-28-32 activity,
-- payer share, revenue per sign-up to date and return on ad spend (ROAS) to date.
-- ClickHouse equivalent: same joins; uniqExactIf(user_id, days_since_signup BETWEEN 28 AND 32).
with cohort as (
    select * from users where signup_date between date '2026-05-01' and date '2026-07-31'
),
spend as (
    select channel, sum(spend_usd) as spend from ua_spend
    where date between date '2026-05-01' and date '2026-07-31' group by channel
),
d30 as (select distinct user_id from daily_activity where days_since_signup between 28 and 32),
rev as (select user_id, sum(revenue_usd) as revenue from subscriptions group by user_id)
select c.channel,
       count(*)                                                   as signups,
       round(coalesce(s.spend, 0) / count(*), 2)                  as cost_per_signup,
       round(avg((d.user_id is not null)::int), 4)                as active_d28_32,
       round(avg((r.user_id is not null)::int), 4)                as payer_share,
       round(sum(coalesce(r.revenue, 0)) / count(*), 2)           as revenue_per_signup,
       round(sum(coalesce(r.revenue, 0)) / nullif(s.spend, 0), 2) as roas_to_date
from cohort c
left join spend s using (channel)
left join d30 d using (user_id)
left join rev r using (user_id)
group by c.channel, s.spend
order by revenue_per_signup desc;

-- 05 Revenue per user (ARPU) and per payer (ARPPU) by monthly sign-up cohort, 30 days after sign-up.
-- One subscription row is expanded into one row per payment (range join); a refunded first payment counts 0.
-- Only payments made <= 30 days after sign-up count. Boosts (consumables) are added from the event log.
-- ClickHouse equivalent: arrayJoin(range(paid_periods)) to expand payments, then sumIf by window.
with payments as (
    select s.user_id,
           s.first_payment_date + to_days(cast(k * s.period_days as integer))       as paid_on,
           s.price_usd - case when s.refunded and k = 0 then s.price_usd else 0 end as amount
    from subscriptions s, range(0, 60) t(k)
    where k < s.paid_periods
),
boosts as (
    select user_id, cast(event_time as date) as paid_on, cast(prop as double) as amount
    from events where event_name = 'boost_purchase'
),
rev30 as (
    select u.user_id, date_trunc('month', u.signup_date) as cohort_month,
           coalesce(sum(p.amount), 0) as revenue_30d
    from users u
    left join (select * from payments union all select * from boosts) p
           on p.user_id = u.user_id and p.paid_on <= u.signup_date + interval 30 day
    where u.signup_date <= date '2026-10-01'
    group by all
)
select cohort_month,
       count(*)                                                                         as users,
       round(sum(revenue_30d), 0)                                                       as revenue_30d,
       round(avg(revenue_30d), 3)                                                       as arpu_30d,
       round(sum(revenue_30d) / nullif(count(*) filter (where revenue_30d > 0), 0), 2) as arppu_30d,
       round(avg((revenue_30d > 0)::int), 4)                                            as payer_share_30d
from rev30
group by cohort_month
order by cohort_month;

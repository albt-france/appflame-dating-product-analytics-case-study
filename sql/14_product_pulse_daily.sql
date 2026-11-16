-- 14 Product pulse, one row per day: sign-ups, activations, daily active users, matches, new conversations,
-- new payers and revenue (payments booked that day, refunds netted). Feeds the dashboard.
-- ClickHouse equivalent: uniqExact(user_id) for DAU, toDate(event_time) for the day, arrayJoin for payments.
with days as (
    select unnest(generate_series(date '2026-05-01', date '2026-10-31', interval 1 day))::date as d
),
s as (select signup_date::date as d, count(*) as signups from users group by 1),
a as (
    select activity_date::date as d, count(*) as dau, sum(matches) as matches, sum(messages_sent) as messages
    from daily_activity group by 1
),
e as (
    select event_time::date as d,
           count(*) filter (where event_name = 'first_conversation') as new_conversations,
           count(*) filter (where event_name = 'subscription_start') as new_payers,
           count(*) filter (where event_name = 'activated')          as activated
    from events group by 1
),
r as (
    select s2.first_payment_date + to_days(cast(k * s2.period_days as integer)) as d,
           sum(s2.price_usd - case when s2.refunded and k = 0 then s2.price_usd else 0 end) as revenue
    from subscriptions s2, range(0, 60) t(k) where k < s2.paid_periods group by 1
)
select days.d as date,
       coalesce(signups, 0) as signups, coalesce(activated, 0) as activated, coalesce(dau, 0) as dau,
       coalesce(matches, 0) as matches, coalesce(messages, 0) as messages,
       coalesce(new_conversations, 0) as new_conversations, coalesce(new_payers, 0) as new_payers,
       round(coalesce(revenue, 0), 2) as revenue_usd
from days
left join s on s.d = days.d
left join a on a.d = days.d
left join e on e.d = days.d
left join r on r.d = days.d
order by date;

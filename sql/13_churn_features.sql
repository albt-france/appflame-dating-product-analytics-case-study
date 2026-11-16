-- 13 Subscriber churn features: one row per paid subscription whose first renewal date is observable
-- (on or before 31 Oct). Target = cancelled after the first paid period (did not renew).
-- Features use only the first 7 days after the subscription started, so a model can act before renewal.
-- ClickHouse equivalent: same joins; sumIf(..., activity_date < started_at + INTERVAL 7 DAY).
with s as (
    select * from subscriptions
    where paid_periods >= 1
      and first_payment_date + to_days(cast(period_days as integer)) <= date '2026-10-31'
),
w as (
    select s.subscription_id,
           count(a.activity_date)             as active_days_7d,
           coalesce(sum(a.matches), 0)        as matches_7d,
           coalesce(sum(a.messages_sent), 0)  as messages_7d,
           coalesce(sum(a.likes_received), 0) as likes_received_7d,
           coalesce(sum(a.swipes), 0)         as swipes_7d
    from s left join daily_activity a
      on a.user_id = s.user_id
     and a.activity_date >= s.started_at and a.activity_date < s.started_at + interval 7 day
    group by s.subscription_id
)
select s.subscription_id, s.plan, s.price_usd, s.trial, u.country, u.platform, u.channel, u.market_side,
       date_diff('day', u.signup_date, s.started_at) as days_signup_to_sub,
       w.active_days_7d, w.matches_7d, w.messages_7d, w.likes_received_7d, w.swipes_7d,
       (s.paid_periods = 1 and s.status = 'cancelled')::int as churned_first_period
from s join w using (subscription_id) join users u using (user_id);

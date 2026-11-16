-- 09 Experiment read-out, paywall price test (E1): per user, revenue on day 1 and within 30 days of assignment,
-- and paid-within-30-days flag. Python then computes means, confidence intervals and the decision.
-- Only users assigned on or before 1 Oct have a complete 30-day window (all of E1: 1 Jul - 25 Aug).
-- ClickHouse equivalent: sumIf(amount, paid_on <= toDate(assigned_at) + 30) per user; welchTTest(rev_d30, variant = 'treatment').
with a as (
    select user_id, variant, cast(assigned_at as date) as assigned_on
    from experiments where experiment_id = 'E1_paywall_price'
),
pay as (
    select s.user_id,
           s.first_payment_date + to_days(cast(k * s.period_days as integer))       as paid_on,
           s.price_usd - case when s.refunded and k = 0 then s.price_usd else 0 end as amount
    from subscriptions s, range(0, 60) t(k) where k < s.paid_periods
)
select a.user_id, a.variant, a.assigned_on,
       coalesce(sum(p.amount) filter (where p.paid_on <= a.assigned_on + 1), 0)  as rev_d1,
       coalesce(sum(p.amount) filter (where p.paid_on <= a.assigned_on + 7), 0)  as rev_d7,
       coalesce(sum(p.amount) filter (where p.paid_on <= a.assigned_on + 30), 0) as rev_d30,
       coalesce(max(case when p.paid_on <= a.assigned_on + 30 then 1 end), 0)    as paid_d30,
       coalesce(max(case when p.paid_on <= a.assigned_on + 1 then 1 end), 0)     as paid_d1
from a left join pay p using (user_id)
group by a.user_id, a.variant, a.assigned_on;

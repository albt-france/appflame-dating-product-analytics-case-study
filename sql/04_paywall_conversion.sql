-- 04 Paywall: share of sign-ups who saw it and who paid within 30 days of sign-up, by platform and country.
-- Users who signed up after 1 Oct are excluded (their 30-day window is not complete).
-- ClickHouse equivalent: uniqExactIf(user_id, event_name = 'subscription_start' AND dateDiff('day', signup_ts, event_time) <= 30).
with base as (
    select user_id, platform, country, signup_ts
    from users where signup_date <= date '2026-10-01'
),
viewed as (select distinct user_id from events where event_name = 'paywall_view'),
paid30 as (
    select distinct e.user_id
    from events e join base b using (user_id)
    where e.event_name = 'subscription_start'
      and date_diff('day', b.signup_ts, e.event_time) <= 30
)
select b.platform, b.country,
       count(*)                                                                                 as signups,
       round(avg((v.user_id is not null)::int), 4)                                              as paywall_view_rate,
       round(avg((p.user_id is not null)::int), 4)                                              as paid_within_30d_rate,
       round(sum((p.user_id is not null)::int) / nullif(sum((v.user_id is not null)::int), 0), 4) as paid_per_viewer
from base b
left join viewed v using (user_id)
left join paid30 p using (user_id)
group by all
order by b.platform, b.country;

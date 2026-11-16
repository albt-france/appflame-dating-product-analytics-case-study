-- 03 Activation (onboarding completed and at least one like sent on day 0) and first-day match, by segment.
-- grouping sets returns the country, platform, channel and total rows in one scan.
-- ClickHouse equivalent: uniqExactIf(user_id, event_name = 'activated') / uniqExact(user_id) ... WITH ROLLUP / GROUPING SETS.
with flags as (
    select u.user_id, u.country, u.platform, u.channel,
           max(case when e.event_name = 'onboarding_completed' then 1 else 0 end) as onboarded,
           max(case when e.event_name = 'activated' then 1 else 0 end)            as activated
    from users u
    left join events e on e.user_id = u.user_id and e.event_name in ('onboarding_completed', 'activated')
    group by all
),
d0 as (select user_id, matches > 0 as matched_d0 from daily_activity where days_since_signup = 0)
select f.country, f.platform, f.channel,
       count(*)                                           as signups,
       round(avg(f.onboarded), 4)                         as onboarded_rate,
       round(avg(f.activated), 4)                         as activation_rate,
       round(avg(coalesce(d0.matched_d0, false)::int), 4) as match_day0_rate
from flags f left join d0 using (user_id)
group by grouping sets ((f.country), (f.platform), (f.channel), ())
order by 1, 2, 3;

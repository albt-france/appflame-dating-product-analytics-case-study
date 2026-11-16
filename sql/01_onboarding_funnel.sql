-- 01 Onboarding funnel by platform: share of sign-ups reaching each step, and the step-to-step pass rate.
-- Tables: users, events (event_name = 'onboarding_step', prop = '<n>_<step name>').
-- ClickHouse equivalent: windowFunnel(3600)(event_time, prop = '1_basic_info', prop = '2_birthday', ...) per user,
--   then countIf(level >= k) by platform; uniqExact(user_id) instead of count(distinct user_id).
with steps as (
    select u.platform, e.prop as step, count(distinct e.user_id) as users
    from events e join users u using (user_id)
    where e.event_name = 'onboarding_step'
    group by all
),
signups as (select platform, count(*) as signups from users group by platform)
select s.platform,
       s.step,
       s.users,
       round(s.users / g.signups, 4)                                                   as share_of_signups,
       round(s.users / lag(s.users) over (partition by s.platform order by s.step), 4) as pass_from_previous
from steps s join signups g using (platform)
order by s.platform, s.step;

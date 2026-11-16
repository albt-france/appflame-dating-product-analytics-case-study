-- 02 Retention by weekly sign-up cohort: share of the cohort active on day 1, 7, 14 and 30 after sign-up.
-- Only cohorts old enough to observe day 30 are kept (signed up at least 31 days before 31 Oct).
-- ClickHouse equivalent: toStartOfWeek(signup_date, 1) for the cohort; the retention(d = 0, d = 1, d = 7, d = 30)
--   aggregate returns an array of flags per user in one pass.
with cohort as (
    select user_id, date_trunc('week', signup_date) as cohort_week
    from users
    where signup_date <= date '2026-10-31' - interval 31 day
),
act as (
    select a.user_id, a.days_since_signup as d
    from daily_activity a join cohort c using (user_id)
    where a.days_since_signup in (1, 7, 14, 30)
)
select c.cohort_week,
       count(distinct c.user_id)                                                                 as cohort_size,
       round(count(distinct case when d = 1  then a.user_id end) / count(distinct c.user_id), 4) as d1,
       round(count(distinct case when d = 7  then a.user_id end) / count(distinct c.user_id), 4) as d7,
       round(count(distinct case when d = 14 then a.user_id end) / count(distinct c.user_id), 4) as d14,
       round(count(distinct case when d = 30 then a.user_id end) / count(distinct c.user_id), 4) as d30
from cohort c left join act a on a.user_id = c.user_id
group by c.cohort_week
order by c.cohort_week;

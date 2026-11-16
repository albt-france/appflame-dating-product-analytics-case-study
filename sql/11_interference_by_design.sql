-- 11 Matching feature (E3): matches per user during the test (1-28 Sep) and in the 4 weeks before (pre-period),
-- by randomisation design (users split inside a metro vs whole metros) and variant, one row per metro.
-- The pre-period shows the groups were comparable; Python analyses the metro design at metro level.
-- ClickHouse equivalent: sumIf(matches, activity_date BETWEEN ...) GROUP BY unit, variant, cluster.
with a as (
    select user_id, variant, unit, cluster as metro from experiments where experiment_id = 'E3_smart_picks'
),
m as (
    select user_id,
           sum(matches) filter (where activity_date between date '2026-09-01' and date '2026-09-28') as matches_test,
           sum(matches) filter (where activity_date between date '2026-08-04' and date '2026-08-31') as matches_pre
    from daily_activity group by user_id
)
select a.unit as design, a.variant, a.metro,
       count(*)                                   as users,
       round(avg(coalesce(m.matches_test, 0)), 4) as matches_per_user_test,
       round(avg(coalesce(m.matches_pre, 0)), 4)  as matches_per_user_pre
from a left join m using (user_id)
group by all
order by design, variant, metro;

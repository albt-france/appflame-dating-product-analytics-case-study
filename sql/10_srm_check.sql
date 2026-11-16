-- 10 Sample-ratio mismatch (SRM) check for every user-randomised experiment, overall and by platform.
-- Expected split 50/50. Chi-square with 1 degree of freedom computed in SQL; p-value added in Python
-- (scipy.stats.chi2.sf). chi2 > 10.83 means p < 0.001: do not read the result, find the bug first.
-- ClickHouse equivalent: countIf(variant = 'treatment'), countIf(variant = 'control') GROUP BY experiment_id, platform.
with c as (
    select e.experiment_id, u.platform,
           count(*) filter (where variant = 'treatment') as n_t,
           count(*) filter (where variant = 'control')   as n_c
    from experiments e join users u using (user_id)
    where e.unit = 'user'
    group by grouping sets ((e.experiment_id, u.platform), (e.experiment_id))
)
select experiment_id, coalesce(platform, 'all') as platform, n_t, n_c,
       round(n_t / (n_t + n_c), 4)                                   as share_treatment,
       round(power(n_t - (n_t + n_c) / 2, 2) / ((n_t + n_c) / 2)
           + power(n_c - (n_t + n_c) / 2, 2) / ((n_t + n_c) / 2), 2) as chi2
from c
order by experiment_id, platform;

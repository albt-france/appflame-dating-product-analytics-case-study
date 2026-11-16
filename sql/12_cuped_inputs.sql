-- 12 CUPED inputs for the ice-breaker test (E6): one row per user with the metric during the test
-- (messages sent 1-14 Oct) and the same metric in the two weeks before the test (17-30 Sep), the covariate.
-- The covariate is measured before assignment, so the treatment cannot have changed it.
-- ClickHouse equivalent: sumIf(messages_sent, activity_date BETWEEN ...) per user.
select e.user_id, e.variant,
       coalesce(sum(a.messages_sent) filter (where a.activity_date between date '2026-10-01' and date '2026-10-14'), 0) as y_messages,
       coalesce(sum(a.messages_sent) filter (where a.activity_date between date '2026-09-17' and date '2026-09-30'), 0) as x_pre_messages
from experiments e
left join daily_activity a on a.user_id = e.user_id
where e.experiment_id = 'E6_icebreakers'
group by e.user_id, e.variant;

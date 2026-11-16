-- 06 Like balance: how likes received on the first day are spread across new profiles,
-- and how day-1 / week-1 return differs by bucket. In a two-sided market, if a few profiles get most likes,
-- many new users see nothing on day 0 and leave.
-- ClickHouse equivalent: quantiles(0.5, 0.9, 0.99)(likes_received) for the spread; multiIf() for buckets.
with d0 as (
    select a.user_id, a.likes_received, u.market_side
    from daily_activity a join users u using (user_id)
    where a.days_since_signup = 0
      and u.signup_date <= date '2026-10-24'
      and u.user_id in (select user_id from events where event_name = 'onboarding_completed')
),
ret as (
    select user_id,
           max(case when days_since_signup = 1 then 1 else 0 end)             as back_d1,
           max(case when days_since_signup between 1 and 7 then 1 else 0 end) as back_w1
    from daily_activity group by user_id
),
bucketed as (
    select d0.*, coalesce(r.back_d1, 0) as back_d1, coalesce(r.back_w1, 0) as back_w1,
           case when likes_received = 0 then '0' when likes_received <= 2 then '1-2'
                when likes_received <= 5 then '3-5' when likes_received <= 10 then '6-10' else '11+' end as likes_bucket,
           ntile(10) over (order by likes_received desc) as decile      -- decile 1 = 10% most-liked new profiles
    from d0 left join ret r using (user_id)
),
top as (select sum(likes_received) filter (where decile = 1) / sum(likes_received) as top10_share from bucketed)
select likes_bucket,
       count(*)                                   as users,
       round(count(*) / sum(count(*)) over (), 4) as share_of_users,
       round(avg(back_d1), 4)                     as return_d1,
       round(avg(back_w1), 4)                     as return_week1,
       round(avg((market_side = 'A')::int), 3)    as share_side_a,
       round(any_value(top.top10_share), 3)       as top10pct_share_of_likes
from bucketed, top
group by likes_bucket
order by min(likes_received);

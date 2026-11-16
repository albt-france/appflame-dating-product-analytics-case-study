# E3 — "Smart picks" matching feature: user split vs metro clusters (SIMULATED example)

| | |
|---|---|
| **ID / name** | E3_smart_picks |
| **Dates** | 1 – 28 Sep 2026 (4 weeks), users active during the test who signed up before 1 Sep |
| **Status** | read — decision: extend the cluster test |

## 1. Hypothesis
If the card stack puts first the profiles most likely to like back (reciprocal score), then **matches per active user** will rise,
because a match needs two yes decisions and, in real speed-dating data, interest is rarely mutual (42% say yes, 16% of dates match).

## 2. Metrics
- **Primary:** matches per user during the 4 test weeks.
- **Secondary:** likes received, first messages.
- **Guardrails:** reports per user; matches of users **not** in the treatment (the other side of the market).

## 3. Design
The feature changes **who sees whom**: treated users get more attention partly from the same pool control users draw from.
User randomisation would break the "no interference" assumption (SUTVA). Two designs ran side by side, 40 metros (10 per country):
- **20 metros, user split** (50/50 inside each metro) — what a standard A/B tool does;
- **20 metros, cluster** — whole metros treated (11) or control (9), randomised within country.

## 4. Sample size and duration
Clusters, not users, are the units for the cluster design: the effective sample is 20 metros, so the interval is much wider.
Pre-period (4 weeks before) used to adjust each metro: outcome = test-period matches per user / pre-period matches per user.

## 5. Analysis plan
User-split: Welch t-test on users. Cluster: Welch t-test on the 20 metro ratios (one point per metro). Spill-over check: control users
in user-split metros vs control metros.

## 6. Result
| Read | Control | Treatment | Relative effect [95% CI] | p |
|---|---|---|---|---|
| User split (20 metros, 40,823 users) | 2.85 matches | 3.51 matches | +23.5% [+19.6, +27.4] | <0.001 |
| **Metro clusters (20 metros)** | ratio, 9 metros | ratio, 11 metros | **+3.4% [−0.6, +7.5]** | **0.09** |

## 7. Trust checks
- [x] Pre-period balance (user split): +1.4% [−1.9, +4.6], p = 0.40 — groups were comparable before the test
- [x] **Interference:** control users inside user-split metros made **8% fewer** matches than control users in control metros: the
  treated users' gain was partly taken from them. The +23.5% compares a winner with a loser, not the feature with no feature.
- [x] SRM (user split): p > 0.2
- [ ] Guardrails: reports per user not read in this example (they are in daily_activity.reports; add them to the read-out)

## 8. Decision
**Do not ship on the user-split result.** The unbiased cluster estimate is small and not yet significant (+3.4%, p = 0.09).
Extend the cluster test 4 more weeks (or add metros) before deciding; the mechanism is supported by real data, the size is uncertain.

## 9. Next step
Plan every feature that touches both sides of the market (ranking, boosts, like limits, fair exposure for new profiles) as a cluster or
switchback test from the start, with metro-level power analysis.

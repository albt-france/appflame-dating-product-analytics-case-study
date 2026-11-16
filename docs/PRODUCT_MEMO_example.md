# Product memo — where to grow next (example, SIMULATED "App H" + PUBLIC DATA context)

**To:** product team · **From:** product analytics · **Data:** simulated event log, 1 May – 31 Oct 2026 (200,000 sign-ups); public App Store, review and search data collected 15 Nov 2026.

## Recommendation in one line
Fix the Android photo step this sprint, test day-0 exposure for new profiles by metro next, move push sends to the evening, and stop
two habits that produced wrong decisions: reading tests in the first days, and testing matching features with a user split.

## Three opportunities, ranked by expected impact and effort

| # | Opportunity | Evidence | Expected impact | Effort | First test |
|---|---|---|---|---|---|
| 1 | **Android photo step** | Android users pass it at 66% vs 89% on iOS; the drop is on that one step | ~2,700 more onboarded users a month (~$14K a month at $5.31 revenue per onboarded user to date) | Low: accept more formats, "add photo later" | Android A/B, 5,543 users per arm (~24 days of Android sign-ups); primary: onboarding completion |
| 2 | **Day-0 exposure for new profiles** | 11% of new users get no like on day 0 and return on day 1 at 21% vs 42%; the top 10% of new profiles get 36% of day-0 likes. Real speed-dating data: the top 10% of people get 23% of all yeses | +1 to +2 points of day-1 return on all new users if half of the gap closes (to be measured) | Medium: ranking change | **Metro-cluster test** (it moves attention between users: see E3); primary: day-1 return; guardrail: likes received by existing users |
| 3 | **Evening pushes (19-21h local)** | Send hour is set by a hash of user id (a natural experiment): open rate 8.6% vs 5.9%, same-day return 4.7% vs 3.2% | ~3,200 extra returns a month | Low: scheduler setting | User A/B, 22,435 pushes per arm (~1 week); guardrail: opt-outs |

## What we test first
**Opportunity 1** — highest value per effort, a single-platform user-level test with no interference risk, and it feeds every later
funnel metric. In parallel (different users, different surface): opportunity 3.

## What we stop
- **Reading tests on day 1 or day 7.** The price test looked like "higher price *and* higher conversion" in week 1 (novelty); the
  30-day read shows −10% conversion and +20% revenue per user. Decisions are made on the pre-registered metric at the planned date.
- **User-split tests for matching features.** Smart picks showed +23.5% matches with a user split and +3.4% with metro clusters:
  treated users took matches from control users. Ranking, boosts and like limits go to cluster or switchback tests.
- **Half of the TikTok budget** (geo holdout to confirm): ROAS 0.79 after 90+ days vs 1.04-1.42 for other paid channels; TikTok
  sign-ups are active half as long and pay three times less.
- **Shipping "winners" from batches of tests without correction.** The dark paywall "won" at p = 0.029 among five simultaneous tests;
  after Holm correction (p = 0.14) it is noise.

## Risks and what would change the plan
- The photo-step loss might partly be users who never intended to finish: the A/B test, not the funnel, measures the real gain.
- Fair exposure can lower the experience of the most-liked users: guardrail on their matches and messages.
- Market context (public data): price and paywall clarity is the first complaint theme in written reviews (43-53% vs 32% for peers).
  Any monetisation test watches refunds and 1-star reviews, not only conversion.

# Simulation assumptions (SIMULATED data)

`src/simulate.py`, seed 42, writes a fictional dating app, **"App H"**, to `data/simulated/` (re-created in ~10 s; not committed).
**Nothing here is appflame, Hily or Taimi data.** Levels are plausible orders of magnitude from public sources; effects are planted on
purpose so that each analytical trap is visible. The true effects are written to `data/_hidden_truth.csv`, which the analysis reads only
after every estimate is saved (`src/analysis_product.py`, last step).

## Scope
- 1 May – 31 Oct 2026 (184 days), **200,000 sign-ups**, weekday pattern (Sunday peak) and a mild summer bump.
- 4 countries (US 55%, GB 20%, CA 13%, AU 12%), iOS share 52-60%, 6 channels (organic 35%, Meta 18%, Google UAC 15%, Apple Search Ads 12%, TikTok 12%, influencers 8%), 40 metros (10 per country).
- `market_side` A/B: a **neutral label** (62% / 38%) used only to make the market unbalanced (side B receives ~4x more likes). No gender, no orientation, no sensitive attribute exists in the data.

## Behaviour
| Item | Assumption | Calibration |
|---|---|---|
| Onboarding | 6 steps; pass rates 92-97%, photo step 89% iOS / **66% Android** | Opportunity 1 |
| Activity | P(active on day d) = r · d^−0.36, r from user engagement, channel, day-0 likes, push hour | D1 ≈ 26%, D7 ≈ 13%, D30 ≈ 7.6% of sign-ups (typical dating-app curve) |
| Likes received | Poisson, depends on a hidden appeal score and market side; day-0 boost ×1.4 | 11% of new profiles get none on day 0 |
| Day-0 experience | No like on day 0 → return probability ×0.52 | Opportunity 2 |
| Push hour | Scheduler sets 8-22h from a hash of user id; 19-21h opens ~8.5%, return ×1.10 | Opportunity 3 |
| Channels | Retention multiplier TikTok 0.58 … organic 1.10; payment TikTok 0.55 … Apple Search Ads 1.20; cost per sign-up $2.3-4.6 | Opportunity 4 |
| Paywall | Seen on day 0 by 70% of onboarded users, then when swiping heavily; conversion per view ~4.6% × engagement | 5.6% of sign-ups pay within the period |
| Plans | Weekly $14.99 (55%; = Hily's public US price for "1-week Hily Premium"), monthly $29.99 (35%), quarterly $59.99 (10%); 30% of weekly start with a 3-day trial (52% convert); CA ×0.80, AU ×0.75 price index | Revenue per payer per paid month ≈ $35, between Match Group RPP ($21) and Bumble App ARPPU ($28) on the high side (weekly-heavy, English-speaking markets only) |
| Renewal | Logistic in week-1 matches and active days, plan, trial | Churn model target |
| Refunds | 3% of first payments | — |

## Planted experiments
| Test | Design | True effect |
|---|---|---|
| E1 paywall price | New sign-ups 1 Jul – 25 Aug, $19.99 vs $14.99 | conversion −13%; ×1.30 for treatment in the first test week (novelty); renewal logit −0.15; refunds 4.5% vs 3% |
| E2 onboarding | Sign-ups 3 – 23 Aug | drop-off per step −10% (≈ +3 pts completion); **bug**: Android treatment exposure logged only from step 3 → SRM |
| E3 smart picks | 1 – 28 Sep; 20 metros user split, 20 metros cluster | matches +4% when everyone is treated; treated users get a 1.2× share of a pool shared with control users |
| E4a-e | Five UI tests on September sign-ups | none; assignment seed chosen so exactly one shows p < 0.05 (transparent: written in the hidden truth) |
| E5 profile prompt | October sign-ups, read daily | none; assignment seed chosen so an early daily read crosses p < 0.05 |
| E6 ice-breakers | Users active 17 – 30 Sep, test 1 – 14 Oct | messages +5% |

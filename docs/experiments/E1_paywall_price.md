# E1 — Paywall price $19.99 vs $14.99 (SIMULATED example)

| | |
|---|---|
| **ID / name** | E1_paywall_price |
| **Dates** | 1 Jul – 25 Aug 2026 (8 weeks, all new sign-ups); read on 30 Sep, once every user had 30 days |
| **Status** | decided |

## 1. Hypothesis
If the weekly plan moves from $14.99 to $19.99 (+33%, same for monthly and quarterly plans), then **30-day revenue per assigned user** will rise,
because the price elasticity of dating subscriptions is low: conversion should fall by less than the price rises. Public anchor: Hily's
US App Store lists "1-week Hily Premium" at $14.99 and "1 week Premium+" at $24.99 (15 Nov 2026).

## 2. Metrics
- **Primary:** revenue in the 30 days after assignment (sign-up), per assigned user, net of refunds.
- **Secondary:** conversion to paid within 30 days; revenue on day 1 and day 7.
- **Guardrails:** refund rate (alert if +1 point), first renewal rate, share active on days 28-32 (alert if −1 point).

## 3. Design
User-level randomisation at sign-up (hash of user id + salt `paywall_price_v2`), 50/50. A price shown to one user does not change what
other users see, so user randomisation is valid here.

## 4. Sample size and duration
Pre-period May-June: revenue per user $1.66 (sd $8.92: 96% of users pay nothing), conversion 4.2%.
- +8% would need 70,941 users per arm (155 days of traffic): too long.
- **MDE chosen: +12% → 31,530 users per arm → 8 weeks.** Achieved: 32,351 vs 32,286 users (MDE 11.6%).

## 5. Analysis plan
Welch t-test on revenue per user, z-test on conversion, delta-method CI for the relative effect. No early stop. Segments: platform only.

## 6. Result
| Metric | Control $14.99 | Treatment $19.99 | Relative effect [95% CI] | p |
|---|---|---|---|---|
| Conversion to paid, 30 days | 4.41% | 3.96% | −10.2% [−16.9, −3.6] | 0.004 |
| Revenue per user, day 1 | $0.60 | $0.75 | +25.9% [+11.4, +40.5] | <0.001 |
| **Revenue per user, day 30** | **$1.73** | **$2.08** | **+20.4% [+10.3, +30.4]** | **<0.001** |
| Refund rate (payers) | 3.0% | 4.7% | +1.7 pts | 0.005 |
| First renewal | 60.8% | 58.9% | −1.9 pts | — |
| Active days 28-32 | 30.2% | 29.9% | −0.3 pts | — |

## 7. Trust checks
- [x] SRM: 50.05% treatment, p = 0.80
- [x] Novelty: in the **first week**, treatment conversion looked **higher** (+23%, p = 0.13) — curiosity about a new paywall. It turned negative from week 2. A day-7 read would have said "higher price and higher conversion".
- [x] Peeking: one read, at the planned date
- [x] Guardrails: refund rate breached the +1 point alert (+1.7 pts); retention and renewal inside thresholds
- [x] Interference: none expected (price is private to the user)

## 8. Decision
**Ship $19.99**, with a clearer price screen (total price and renewal period above the button) because refunds rose; they are already
netted out of revenue, so the +20% is a net gain. Expected effect: +$0.35 revenue per new user in 30 days [+$0.19, +$0.51].

## 9. Next step
Monitor revenue per user at day 90 (renewals come later and are slightly lower), refunds weekly, and 1-star reviews mentioning price
(public reviews show price is already the first complaint theme). Then test the price-screen copy against refunds.

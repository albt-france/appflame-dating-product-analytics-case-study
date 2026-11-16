# Experiment read-out — one page

> Copy this file to `docs/experiments/<id>_<name>.md`. Fill sections 1-5 **before launch** (they are the pre-registration);
> fill 6-9 after the planned end date only. Two filled examples: [E1 paywall price](experiments/E1_paywall_price.md),
> [E3 smart picks](experiments/E3_smart_picks.md).

| | |
|---|---|
| **ID / name** | |
| **Owner / reviewers** | |
| **Dates** | planned start – planned end (no early stop unless a guardrail breaks or a sequential boundary is crossed) |
| **Status** | draft · running · read · decided |

## 1. Hypothesis
If **[change]**, then **[primary metric]** will **[direction and size]**, because **[evidence: data, research, user feedback]**.

## 2. Metrics
- **Primary (one only):** definition, window (e.g. 30 days after assignment), unit (per assigned user).
- **Secondary:** metrics that explain the mechanism (not used for the decision).
- **Guardrails:** metrics that must not get worse (refunds, reports, retention, the other side of the market). Threshold for each.

## 3. Design
- **Unit of randomisation:** user · device · metro / cluster · time slot (switchback). In a two-sided product, ask: *can treated users change what control users see?* If yes, randomise clusters.
- **Population and exposure point:** who is eligible; where the exposure event is logged (must be the same for both variants).
- **Split:** 50/50 unless a reason is written here. Assignment = deterministic hash of the unit id + salt.

## 4. Sample size and duration
- Baseline from a pre-period: mean, standard deviation (or rate).
- Minimum detectable effect (relative), α = 5% two-sided, power 80%: **n per arm =** 2(z₀.₉₇₅ + z₀.₈)²σ²/δ² (means) or the two-proportion formula (rates).
- Variance reduction planned (CUPED covariate: same metric before assignment)?
- Duration = n / eligible traffic per day, rounded up to full weeks (weekday effects). **Planned end date:**

## 5. Analysis plan
Test (Welch t-test / two-proportion z-test / metro-level test), confidence interval reported for the relative effect (delta method),
segments decided in advance (max 2), correction if several primary comparisons (Holm), what would make the result invalid.

## 6. Result (at the planned end date)
| Metric | Control | Treatment | Relative effect [95% CI] | p |
|---|---|---|---|---|

## 7. Trust checks
- [ ] **SRM:** chi-square on assignment counts, overall and by platform / country (stop if p < 0.001)
- [ ] **Pre-period balance:** primary metric before assignment, same in both groups
- [ ] **Novelty / primacy:** effect by assignment week or day since exposure
- [ ] **Peeking:** read only at the planned end, or with a sequential boundary (O'Brien-Fleming)
- [ ] **Multiple tests:** number of comparisons, Holm or Benjamini-Hochberg applied
- [ ] **Interference:** spill-over to control users (control in mixed clusters vs pure control clusters)
- [ ] **Guardrails** inside thresholds

## 8. Decision
Ship · iterate · stop · re-run — and why, in two sentences. Expected impact on the business metric (with interval).

## 9. Next step
Follow-up test, monitoring after launch (e.g. revenue at day 90), owner and date.

# Tableau build guide

The workbook [`tableau/AppH_Product_Analytics.twbx`](../tableau/AppH_Product_Analytics.twbx) holds 4 dashboards (1366 × 768) built on
8 extracts. It opens in the free **Tableau Public** desktop app (checked with Tableau Public 2026.3).

| Dashboard | Data | What it answers |
|---|---|---|
| 1 Product pulse | `pulse` (day × country × platform) | Sign-ups, activation, matches, payers, revenue; trends by week |
| 2 Funnel & cohorts | `funnel`, `retention` | Where sign-ups drop (by platform), retention curves by monthly cohort, quality by channel |
| 3 Experiments | `experiments` | Every read of the 6 tests with its 95% interval, SRM flag and decision |
| 4 Market view | `market_ratings`, `market_prices`, `review_themes`, `trends` | PUBLIC DATA: ratings, prices, review themes, search interest vs peers |

## 1. Rebuild the files
```
python src/export_tableau.py     # data/output/tableau/*.csv + *.hyper (Tableau Public only saves extract-based workbooks)
python src/build_tableau.py      # tableau/AppH_Product_Analytics.twb + .twbx (packaged, relative paths)
```
`src/build_tableau.py` writes the workbook XML with a small writer (`src/twb.py`); every calculated field is declared there with the
same formula you would type in Tableau.

## 2. Publish to Tableau Public (manual, needs your own neutral profile)
1. Open `tableau/AppH_Product_Analytics.twbx` in Tableau Public.
2. Check each dashboard tab; set *Country* and *Platform* on dashboards 1-2.
3. **File › Save to Tableau Public As…**, name it `AppH Product Analytics`.
4. On the web page: *Edit details* → add the description "Independent case study based on public data · not affiliated with or endorsed by appflame. Views 1-3 SIMULATED, view 4 PUBLIC DATA."
5. Copy the link into the README (section *Dashboard*).

## 3. Rebuild each view by hand (to explain it in an interview)
**Parameters** — *Country* (string list: All, US, GB, CA, AU) and *Platform* (All, ios, android).
**Filter field (pulse, funnel, retention)** — `In scope` =
`([Parameters].[Country] = "All" OR [country] = [Parameters].[Country]) AND ([Parameters].[Platform] = "All" OR [platform] = [Parameters].[Platform])`
→ put on Filters, keep *True*, show both parameter controls.

### Dashboard 1 — Product pulse
- KPI cards: Text marks with `KPI sign-ups` = `STR(ROUND(SUM([signups]) / 1000, 1)) + "K"`, `KPI activation` = `STR(ROUND(SUM([activated]) / SUM([signups]) * 100, 1)) + "%"`, same pattern for matches, payers and revenue.
- *Sign-ups and DAU*: Columns `WEEK(date)` (continuous), Rows `Avg DAU` = `SUM([dau]) / COUNTD([date])` (bars) and `Avg daily sign-ups` = `SUM([signups]) / COUNTD([date])` (line), dual axis. Filter `Full weeks` = `[date] < #2026-10-25#` drops the last partial week.
- *Revenue weekly*, *Payers weekly*: `WEEK(date)` × `SUM(revenue_usd)` / `SUM(new_payers)`.
- *Activation by platform*: `Activation rate` = `SUM([activated]) / SUM([signups])` by platform.

### Dashboard 2 — Funnel & cohorts
- *Funnel*: Rows `stage_order`, `stage`, `platform`; Columns `Share of sign-ups` = `SUM([users]) / SUM([Sign-ups (EXCLUDE stage)])` with
  `Sign-ups (EXCLUDE stage)` = `{EXCLUDE [stage], [stage_order] : SUM(IF [stage_order] = 1 THEN [users] END)}`.
  EXCLUDE (not FIXED) so the denominator still follows the country / platform / channel filters.
- *Retention curves*: Columns `day_since_signup` (discrete), Rows `Retention` = `SUM([active_users]) / SUM([cohort_size])`, Color `Cohort`;
  filter `Curve window` = `[fully_observed] AND [day_since_signup] >= 1 AND [day_since_signup] <= 30`.
- *Day-7 by channel*: `SUM(IF [day_since_signup] = 7 THEN [active_users] END) / SUM(IF [day_since_signup] = 7 THEN [cohort_size] END)`.
- *Paid share by channel*: `SUM(IF [stage_order] = 11 THEN [users] END) / SUM(IF [stage_order] = 1 THEN [users] END)`.

### Dashboard 3 — Experiments
- *Forest*: Gantt bar, Rows `Test` = `[experiment] + "  ·  " + [read]`, Columns `SUM(ci_low)`, Size `CI width` = `SUM([ci_high]) - SUM([ci_low])`,
  Color `Verdict` (misleading read / effect / no clear effect), Label `Effect txt`.
- *Read-out table*: Rows experiment, read, decision; Text = effect [CI] · p · SRM flag.

### Dashboard 4 — Market view (PUBLIC DATA)
- *Ratings US*: filter `country = "us"`, bars `SUM(rating_count)` by app, colour Hily / Taimi vs peers, label `AVG(avg_rating)`.
- *Prices*: Columns country, app; Rows `SUM(price_usd)` (ECB rates of 13 Nov 2026; GB, DE, FR include VAT).
- *Review themes*: Square marks, Rows theme, Columns app group, Colour and Text `AVG(share)`.
- *Trends*: `WEEK(date)` × `SUM(interest)`, colour term, filter Hily, Taimi, HER app.

## 4. Fallback
If Tableau is not available, [`docs/dashboard.html`](dashboard.html) shows the same 4 views from the same extracts (Plotly, one file, offline).

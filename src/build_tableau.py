"""Build tableau/AppH_Product_Analytics.twb (+ packaged .twbx): 4 dashboards on the extracts written by
src/export_tableau.py. Open the .twbx in Tableau Public (free) and use File > Save to Tableau Public.

    python src/build_tableau.py

Every calculated field below is the formula you would type in Tableau (Analysis > Create Calculated Field);
docs/TABLEAU_BUILD.md explains how to rebuild each view by hand.
"""
import json
import zipfile

from common import OUT, ROOT, utf8
from twb import Dashboard, DataSource, Sheet, Workbook

DATA = (OUT / "tableau").as_posix()
TWB = ROOT / "tableau" / "AppH_Product_Analytics.twb"
SCHEMAS = json.loads((OUT / "tableau" / "schemas.json").read_text())
BLUE, LIGHT, DARK, GREY, LGREY, RED = "#2a78d6", "#86b6ef", "#104281", "#898781", "#d6d4cc", "#d03b3b"
P = "[Parameters]"
SIM_FOOT = "SIMULATED data: fictional dating app 'App H', 1 May - 31 Oct 2026, seed 42. Not appflame, Hily or Taimi data.  ·  Independent case study, not affiliated with or endorsed by appflame"
PUB_FOOT = "PUBLIC DATA: Apple App Store (lookup API, store pages, review RSS) and Google Trends, collected 15 Nov 2026; ECB rates 13 Nov 2026.  ·  Independent case study, not affiliated with or endorsed by appflame"

wb = Workbook()
wb.params.add("Country", "string", '"All"', "list", members=['"All"', '"US"', '"GB"', '"CA"', '"AU"'])
wb.params.add("Platform", "string", '"All"', "list", members=['"All"', '"ios"', '"android"'])
SCOPE = f'({P}.[Country] = "All" OR [country] = {P}.[Country]) AND ({P}.[Platform] = "All" OR [platform] = {P}.[Platform])'


def ds(key, caption, captions=None, dims=(), formats=None):
    d = DataSource(f"federated.{key}", caption, DATA, f"{key}.csv", SCHEMAS[key], dims=dims, captions=captions, formats=formats)
    wb.datasources.append(d)
    return d


pulse = ds("pulse", "Product pulse (daily)", {"date": "Day", "signups": "Sign-ups", "dau": "Daily active users",
                                               "new_payers": "New payers", "revenue_usd": "Revenue (USD)", "matches": "Matches",
                                               "platform": "Platform", "country": "Country"})
fun = ds("funnel", "Funnel stages", {"stage": "Stage", "users": "Users", "platform": "Platform", "channel": "Channel"}, dims=("stage_order",))
ret = ds("retention", "Retention by cohort", {"cohort_month": "Cohort month", "day_since_signup": "Days since sign-up", "channel": "Channel"}, dims=("day_since_signup",))
exp = ds("experiments", "Experiment read-outs", {"experiment": "Experiment", "read": "Read"})
rat = ds("market_ratings", "App Store ratings", {"app": "App", "rating_count": "Number of ratings", "avg_rating": "Average rating"})
prc = ds("market_prices", "Subscription prices", {"app": "App", "country": "Storefront", "price_usd": "Price (USD)"})
thm = ds("review_themes", "Review themes", {"app": "App", "theme": "Theme", "share": "Share of reviews"})
trd = ds("trends", "Google Trends US", {"term": "Search term", "interest": "Interest (0-100)", "date": "Week"})

# ---------------------------------------------------------------- calculated fields
for d in (pulse, fun, ret):
    d.dim("In scope", SCOPE, "boolean")
pulse.calc("Activation rate", "SUM([activated]) / SUM([signups])", fmt="p0.0%")
pulse.calc("KPI sign-ups", 'STR(ROUND(SUM([signups]) / 1000, 1)) + "K"', "string", "measure", "nominal")
pulse.calc("KPI activation", 'STR(ROUND(SUM([activated]) / SUM([signups]) * 100, 1)) + "%"', "string", "measure", "nominal")
pulse.calc("KPI matches", 'STR(ROUND(SUM([matches]) / 1000000, 2)) + "M"', "string", "measure", "nominal")
pulse.calc("KPI payers", 'STR(ROUND(SUM([new_payers]) / SUM([signups]) * 100, 1)) + "% of sign-ups"', "string", "measure", "nominal")
pulse.calc("KPI revenue", '"$" + STR(ROUND(SUM([revenue_usd]) / 1000, 0)) + "K"', "string", "measure", "nominal")
pulse.calc("Avg daily sign-ups", "SUM([signups]) / COUNTD([date])", fmt="n#,##0")
pulse.calc("Avg DAU", "SUM([dau]) / COUNTD([date])", fmt="n#,##0")
pulse.dim("Full weeks", "[date] < #2026-10-25#", "boolean")   # Tableau weeks start on Sunday: drop the last partial week
# funnel: share of sign-ups that reach each stage; EXCLUDE keeps the country / platform / channel filters
fun.calc("Sign-ups (EXCLUDE stage)", "{EXCLUDE [stage], [stage_order] : SUM(IF [stage_order] = 1 THEN [users] END)}")
fun.calc("Share of sign-ups", "SUM([users]) / SUM([Sign-ups (EXCLUDE stage)])", fmt="p0%")
fun.calc("Paid share", "SUM(IF [stage_order] = 11 THEN [users] END) / SUM(IF [stage_order] = 1 THEN [users] END)", fmt="p0.0%")
fun.calc("Activation share", "SUM(IF [stage_order] = 8 THEN [users] END) / SUM(IF [stage_order] = 1 THEN [users] END)", fmt="p0%")
ret.calc("Retention", "SUM([active_users]) / SUM([cohort_size])", fmt="p0.0%")
ret.calc("Day-7 retention", "SUM(IF [day_since_signup] = 7 THEN [active_users] END) / SUM(IF [day_since_signup] = 7 THEN [cohort_size] END)", fmt="p0.0%")
ret.dim("Curve window", "[fully_observed] AND [day_since_signup] >= 1 AND [day_since_signup] <= 30", "boolean")
ret.dim("Cohort", 'STR(YEAR([cohort_month])) + "-" + RIGHT("0" + STR(MONTH([cohort_month])), 2)')
ret.dim("Day-7 observable", "[cohort_month] <= #2026-09-01#", "boolean")
exp.calc("CI width", "SUM([ci_high]) - SUM([ci_low])", fmt="p0.0%")
exp.dim("Verdict", 'IF CONTAINS([read], "biased") OR CONTAINS([read], "SRM") OR CONTAINS([read], "misleading") THEN "Misleading read" '
                   'ELSEIF [ci_low] > 0 OR [ci_high] < 0 THEN "Effect (CI excludes 0)" ELSE "No clear effect" END')
exp.calc("Effect txt", 'STR(ROUND(SUM([estimate]) * 100, 1)) + "%  [" + STR(ROUND(SUM([ci_low]) * 100, 1)) + ", " + STR(ROUND(SUM([ci_high]) * 100, 1)) + "]"',
         "string", "measure", "nominal")
exp.calc("p txt", 'IF ISNULL(SUM([p_value])) THEN "" ELSEIF SUM([p_value]) < 0.001 THEN "p < 0.001" ELSE "p = " + STR(ROUND(SUM([p_value]), 3)) END',
         "string", "measure", "nominal")
exp.calc("SRM txt", 'IF ISNULL(SUM([srm_p])) THEN "" ELSEIF SUM([srm_p]) < 0.001 THEN "SRM! p < 0.001" ELSE "SRM ok" END', "string", "measure", "nominal")
exp.dim("Test", '[experiment] + "  ·  " + [read]')
rat.dim("US storefront", '[country] = "us"', "boolean")
rat.dim("Focus app", 'IF [focus] THEN "Hily / Taimi" ELSE "Peer apps" END')
thm.dim("App group", 'IF [app] = "Hily" OR [app] = "Taimi" THEN [app] ELSE "Peers (Tinder, Bumble, Hinge)" END')
thm.calc("Theme share", "AVG([share])", fmt="p0%")
trd.dim("Focus term", '[term] = "Hily" OR [term] = "Taimi" OR [term] = "HER app"', "boolean")

S = wb.sheets.append
SC = [("none:In scope:nk", "true", None)]


def kpi(name, d, caption, value):
    S(Sheet(name, d, mark="Text", filters=SC, label_runs=[(caption, dict(bold=True, size=9, color=GREY)), ("\n", {}),
                                                          ("{" + value + "}", dict(bold=True, size=20))]))


# ---------------------------------------------------------------- 1 Product pulse
kpi("KPI Sign-ups", pulse, "SIGN-UPS", "usr:KPI sign-ups:nk")
kpi("KPI Activation", pulse, "ACTIVATION (LIKE SENT ON DAY 0)", "usr:KPI activation:nk")
kpi("KPI Matches", pulse, "MATCHES", "usr:KPI matches:nk")
kpi("KPI Payers", pulse, "NEW PAYERS", "usr:KPI payers:nk")
kpi("KPI Revenue", pulse, "REVENUE (NET OF REFUNDS)", "usr:KPI revenue:nk")
S(Sheet("Sign-ups and DAU", pulse, title="Daily active users (bars) and daily sign-ups (line), weekly averages", mark="Bar",
        cols=["twk:date:qk"], rows=["usr:Avg DAU:qk"], mark_color=LIGHT, dual=("usr:Avg daily sign-ups:qk", "Line", DARK),
        filters=SC + [("none:Full weeks:nk", "true", None)], axis_titles={"twk:date:qk": " "}))
S(Sheet("Revenue weekly", pulse, title="Revenue per week (USD)", mark="Bar", cols=["twk:date:qk"], rows=["sum:revenue_usd:qk"],
        mark_color=DARK, filters=SC + [("none:Full weeks:nk", "true", None)], axis_titles={"twk:date:qk": " "}))
S(Sheet("Payers weekly", pulse, title="New payers per week", mark="Bar", cols=["twk:date:qk"], rows=["sum:new_payers:qk"],
        mark_color=BLUE, filters=SC + [("none:Full weeks:nk", "true", None)], axis_titles={"twk:date:qk": " "}))
S(Sheet("Activation by platform", pulse, title="Activation rate by platform", mark="Bar", rows=["none:platform:nk"],
        cols=["usr:Activation rate:qk"], color="none:platform:nk", color_map={'"ios"': LIGHT, '"android"': BLUE}, labels=True, filters=SC))

# ---------------------------------------------------------------- 2 Funnel & cohorts
S(Sheet("Funnel", fun, title="Share of sign-ups reaching each stage, by platform (Android drops at the photo step)", mark="Bar",
        rows=["none:stage_order:ok", "none:stage:nk", "none:platform:nk"], cols=["usr:Share of sign-ups:qk"], color="none:platform:nk",
        color_map={'"ios"': LIGHT, '"android"': BLUE}, labels=True, filters=SC))
S(Sheet("Retention curves", ret, title="Share of each monthly cohort active N days after sign-up", mark="Line",
        cols=["none:day_since_signup:ok"], rows=["usr:Retention:qk"], color="none:Cohort:nk",
        filters=SC + [("none:Curve window:nk", "true", None)], axis_titles={"none:day_since_signup:ok": "days since sign-up"}))
S(Sheet("Day-7 by channel", ret, title="Day-7 retention by acquisition channel", mark="Bar", rows=["none:channel:nk"],
        cols=["usr:Day-7 retention:qk"], mark_color=BLUE, labels=True, sort=("none:channel:nk", "usr:Day-7 retention:qk"),
        filters=SC + [("none:Day-7 observable:nk", "true", None)]))
S(Sheet("Paid share by channel", fun, title="Share of sign-ups who ever paid, by channel", mark="Bar", rows=["none:channel:nk"],
        cols=["usr:Paid share:qk"], mark_color=DARK, labels=True, sort=("none:channel:nk", "usr:Paid share:qk"), filters=SC))

# ---------------------------------------------------------------- 3 Experiments
S(Sheet("Forest", exp, title="Relative effect, 95% confidence interval (bar = interval)", mark="GanttBar",
        rows=["none:Test:nk"], cols=["sum:ci_low:qk"], size="usr:CI width:qk", color="none:Verdict:nk",
        color_map={'"Misleading read"': RED, '"Effect (CI excludes 0)"': BLUE, '"No clear effect"': LGREY},
        label_runs=[("{usr:Effect txt:nk}", dict(size=8))], axis_titles={"sum:ci_low:qk": "relative effect"}))
S(Sheet("Read-out table", exp, title="Read-outs, SRM check and decision", mark="Text",
        rows=["none:experiment:nk", "none:read:nk", "none:decision:nk"],
        label_runs=[("{usr:Effect txt:nk}", dict(size=9)), ("  ·  ", dict(size=9, color=GREY)), ("{usr:p txt:nk}", dict(size=9, color=GREY)),
                    ("  ·  ", dict(size=9, color=GREY)), ("{usr:SRM txt:nk}", dict(size=9, color=RED))]))

# ---------------------------------------------------------------- 4 Market view (PUBLIC DATA)
S(Sheet("Ratings US", rat, title="US App Store: number of ratings (label = average rating)", mark="Bar", rows=["none:app:nk"],
        cols=["sum:rating_count:qk"], color="none:Focus app:nk", color_map={'"Hily / Taimi"': BLUE, '"Peer apps"': LGREY},
        label_runs=[("{avg:avg_rating:qk}", dict(size=8))], sort=("none:app:nk", "sum:rating_count:qk"),
        filters=[("none:US storefront:nk", "true", None)], fmt={"avg:avg_rating:qk": "n0.00"}))
S(Sheet("Prices", prc, title="Hily 1-week Premium and Taimi Gold, price in USD by storefront (GB, DE, FR include VAT)", mark="Bar",
        cols=["none:country:nk", "none:app:nk"], rows=["sum:price_usd:qk"], color="none:app:nk",
        color_map={'"Hily"': BLUE, '"Taimi"': DARK}, labels=True, fmt={"sum:price_usd:qk": "c\"$\"#,##0.00"}))
S(Sheet("Review themes", thm, title="Themes in written reviews, last 12 months (share of reviews; darker = more frequent)", mark="Square",
        rows=["none:theme:nk"], cols=["none:App group:nk"], color="usr:Theme share:qk", text="usr:Theme share:qk", labels=True,
        sort=("none:theme:nk", "usr:Theme share:qk")))
S(Sheet("Trends", trd, title="Google Trends, US, weekly (0-100 within one request; names are also first names)", mark="Line",
        cols=["twk:date:qk"], rows=["sum:interest:qk"], color="none:term:nk",
        color_map={'"Hily"': BLUE, '"Taimi"': DARK, '"HER app"': LGREY, '"Grindr"': "#c9c7c0"},
        filters=[("none:Focus term:nk", "true", None)], axis_titles={"twk:date:qk": " "}))


# ---------------------------------------------------------------- dashboards (1366 x 768)
def frame(name, title, subtitle, tag, foot, params=True):
    d = Dashboard(name)
    x = 1236
    if params:
        for pname, w in (("Platform", 120), ("Country", 120))[::1]:
            x -= w + 8
            d.param(pname, x, 12, w, 56)
    d.text([(title, dict(bold=True, size=15)), ("\n", {}), (subtitle, dict(size=10, color=GREY))], 16, 8, x - 24, 66)
    d.text([(tag, dict(bold=True, size=9, color="#ffffff", align="1"))], 1240, 22, 110, 28, bg=RED if tag == "SIMULATED" else BLUE)
    d.text([(foot, dict(size=8, color=GREY))], 16, 742, 1334, 22)
    wb.dashboards.append(d)
    return d


d1 = frame("1 Product pulse", "Product pulse: 200K sign-ups, 58% activate, 5.6% become payers",
           "Daily product KPIs of the simulated app. Pick a country and a platform: every view on this page follows.", "SIMULATED", SIM_FOOT)
for i, n in enumerate(["KPI Sign-ups", "KPI Activation", "KPI Matches", "KPI Payers", "KPI Revenue"]):
    d1.sheet(n, 16 + i * 268, 80, 260, 96, title=False)
d1.sheet("Sign-ups and DAU", 16, 184, 860, 300)
d1.sheet("Activation by platform", 884, 184, 466, 300)
d1.sheet("Revenue weekly", 16, 492, 664, 244)
d1.sheet("Payers weekly", 688, 492, 662, 244)

d2 = frame("2 Funnel & cohorts", "Funnel & cohorts: Android loses a third of users at the photo step; TikTok cohorts fade first",
           "Where sign-ups drop, how cohorts retain, and which channels bring users who stay and pay.", "SIMULATED", SIM_FOOT)
d2.sheet("Funnel", 16, 80, 664, 400)
d2.sheet("Retention curves", 688, 80, 662, 400)
d2.sheet("Day-7 by channel", 16, 488, 664, 248)
d2.sheet("Paid share by channel", 688, 488, 662, 248)

d3 = frame("3 Experiments", "Experiments: three reads were misleading (day 1, SRM, interference); the right reads drive the decisions",
           "Each line is one read of a test. Red = a read that would have led to a wrong decision. Intervals are 95% confidence intervals.",
           "SIMULATED", SIM_FOOT, params=False)
d3.sheet("Forest", 16, 80, 640, 656)
d3.sheet("Read-out table", 664, 80, 686, 656, fit="fit-width")

d4 = frame("4 Market view", "Market view: Hily and Taimi rate 4.4★ like the leaders; price and fake-profile complaints stand out",
           "Public App Store, price and search data for Hily, Taimi and peer dating apps.", "PUBLIC DATA", PUB_FOOT, params=False)
d4.sheet("Ratings US", 16, 80, 664, 326)
d4.sheet("Prices", 688, 80, 662, 326)
d4.sheet("Review themes", 16, 412, 664, 324)
d4.sheet("Trends", 688, 412, 662, 324)


def main():
    utf8()
    TWB.parent.mkdir(parents=True, exist_ok=True)
    import sys
    if "--previews" in sys.argv:          # one local copy per dashboard, opening on it (screenshots only, not committed)
        for i in range(len(wb.dashboards)):
            wb.active = i
            wb.write(TWB.with_name(f"_preview_{i + 1}.twb"))
        wb.active = 0
    wb.write(TWB)
    print(f"written {TWB.relative_to(ROOT)}  ({len(wb.sheets)} sheets, {len(wb.dashboards)} dashboards)")
    twbx = TWB.with_suffix(".twbx")       # packaged: workbook + extracts with relative paths, opens anywhere
    xml = TWB.read_text(encoding="utf-8").replace(DATA, "Data/Extracts")
    with zipfile.ZipFile(twbx, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(TWB.name, xml)
        for f in sorted((OUT / "tableau").glob("*")):
            if f.suffix in (".hyper", ".csv"):
                z.write(f, f"Data/Extracts/{f.name}")
    TWB.write_text(xml, encoding="utf-8")   # the loose .twb also uses relative paths (no local folder in the file)
    print(f"written {twbx.relative_to(ROOT)}  ({twbx.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()

"""Write and execute notebooks/appflame_analysis.ipynb (the single notebook of the study).

    python src/make_notebook.py

The notebook re-runs the key steps live (SQL, statistics, models) with the functions in src/, so every number can be traced.
"""
import nbformat as nbf
from nbconvert.preprocessors import ExecutePreprocessor

from common import ROOT, utf8

NB = ROOT / "notebooks" / "appflame_analysis.ipynb"
cells = []


def md(t):
    cells.append(nbf.v4.new_markdown_cell(t.strip()))


def code(t):
    cells.append(nbf.v4.new_code_cell(t.strip()))


md("""
# appflame: finding and testing growth opportunities in Hily and Taimi

One notebook, in the order of the job: **look at the market → listen to users → find opportunities → turn them into hypotheses →
design and read tests → model churn**. Two kinds of data, always labelled:

- **PUBLIC DATA**: App Store (Apple APIs and pages), written reviews (aggregates only), Google Trends, ECB rates, the Columbia speed-dating experiment.
- **SIMULATED**: "App H", a fictional dating app (200,000 sign-ups, 6 months, seed 42). Never appflame, Hily or Taimi data.

Run order: `src/download_data.py` → `src/simulate.py` → `src/analysis_public.py` → `src/analysis_product.py` → this notebook.
""")
code("""
import sys, json
from pathlib import Path
ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(ROOT / "src"))
import numpy as np, pandas as pd
import ab_stats as ab
from common import OUT, PUB, sim_con
from run_sql import run
pd.set_option("display.precision", 3); pd.set_option("display.width", 140)
P = json.loads((OUT / "public_results.json").read_text()); S = json.loads((OUT / "product_results.json").read_text())
con = sim_con()
""")

md("## 1. Hily and Taimi in public data (PUBLIC DATA)\nPublished facts are quoted *as stated by the company*, with the page and the date.")
code("""pd.read_csv(PUB / "company_facts.csv")[["entity", "fact", "value", "seen_on"]]""")
code("""
r = pd.read_csv(OUT / "pub_ratings_us.csv")[["app", "avg_rating", "rating_count", "current_version_date"]]
r.sort_values("rating_count", ascending=False)
""")
md("Same item, six storefronts, converted with ECB rates. GB, DE and FR prices include VAT; US, CA and AU store prices exclude sales tax.")
code("""pd.read_csv(OUT / "pub_price_by_country.csv")""")
code("""print(json.dumps(P["trends"], indent=1)); print("release rhythm (versions seen in reviews per 30 days):", P["reviews"]["cadence"])""")

md("""
## 2. What users say (PUBLIC DATA)
Transparent keyword rules (`src/analysis_public.py`, `THEMES`), multi-label. Checked on 45 reviews labelled by hand
(`data/public/review_validation_labels.csv`, ids only). Written reviews are a negative, self-selected sample: read **themes**, not satisfaction.
""")
code("""pd.read_csv(OUT / "pub_review_validation.csv")""")
code("""
th = pd.read_csv(OUT / "pub_review_themes.csv").pivot(index="theme", columns="app", values="share")
th["peers"] = th[["Tinder", "Bumble", "Hinge"]].mean(axis=1)
th[["Hily", "Taimi", "peers"]].sort_values("Hily", ascending=False).style.format("{:.0%}")
""")

md("""
## 3. What makes a match mutual (PUBLIC DATA, speed-dating experiment)
One row per pair, target = both said yes. Three feature sets: profile only → + behaviour history (leave-one-out yes-rates) → + ratings
after meeting. Cross-validation holds out whole sessions (`GroupKFold`), so no person is in both train and test.
**Not used:** race, religion, origin, income, gender.
""")
code("""
sd = P["speed_dating"]
print(f"yes rate {sd['yes_rate']:.1%} | match rate {sd['match_rate']:.1%} | if independent {sd['independent_match']:.1%} | corr(dec, dec_o) {sd['corr_dec']:+.3f}")
print(f"top 10% most-liked people receive {sd['top10_share_yes']:.0%} of all yeses")
pd.read_csv(OUT / "pub_sd_models.csv")
""")
code("""pd.read_csv(OUT / "pub_sd_coefs.csv").head(8)  # standardised logistic coefficients, full model""")
code("""pd.read_csv(OUT / "pub_sd_by_shared.csv")""")
md("""
**Product translation.** (1) Rank pairs on *both* sides' probability of saying yes, using like-back history: behaviour adds far more than
profile fields. (2) Attention concentrates naturally: new profiles need guaranteed exposure. (3) *Perceived* shared interests drive
matches much more than measured overlap: prompts and ice-breakers that surface common ground (tested in E6).
""")

md("## 4. Where the growth is (SIMULATED)\nEach opportunity comes from one SQL query in `sql/` and ends as a testable hypothesis.")
code("""run("01_onboarding_funnel.sql", con)""")
code("""run("06_like_balance.sql", con)""")
code("""run("07_push_hour.sql", con).iloc[[0, 4, 11, 12, 13, 14]]""")
code("""run("08_channel_quality.sql", con)""")
code("""
for k, o in S["opportunities"].items():
    print(f"[{k}] {o['hypothesis']}\\n    primary: {o['metric']} | guardrails: {o['guardrails']}"
          + (f" | n per arm: {o['n_per_arm']:,}" if "n_per_arm" in o else "") + (f" | design: {o['design']}" if "design" in o else "") + "\\n")
""")

md("""
## 5. A/B tests, end to end (SIMULATED)
### 5.1 Size before launch (E1 paywall price)
n per arm = 2 (z₀.₉₇₅ + z₀.₈)² σ² / δ², with σ and the mean taken from a pre-period without any test.
""")
code("""
base = run("05_revenue_per_user_payer.sql", con)
pre = S["E1"]["pre"]
for mde in (0.05, 0.08, 0.12):
    n = ab.sample_size_mean(pre["mean"], pre["sd"], mde)
    print(f"MDE {mde:.0%}: {n:,} users per arm = {2 * n / pre['signups_per_day']:.0f} days of traffic")
""")
md("### 5.2 Read E1 on the pre-registered metric (30-day revenue), not on day 1")
code("""
e1 = run("09_experiment_readout.sql", con)
t, c = e1[e1.variant == "treatment"], e1[e1.variant == "control"]
rows = {m: ab.mean_test(t[m], c[m]) for m in ("rev_d1", "rev_d7", "rev_d30")}
rows["paid_d30"] = ab.prop_test(t.paid_d30.sum(), len(t), c.paid_d30.sum(), len(c))
pd.DataFrame(rows).T[["rel", "rel_low", "rel_high", "p"]]
""")
code("""pd.read_csv(OUT / "p_e1_weekly.csv")  # novelty: week 1 conversion is up, then down""")
md("### 5.3 Check the split first: sample-ratio mismatch (E2 onboarding)")
code("""
srm = run("10_srm_check.sql", con)
srm["p"] = [ab.srm_test(a, b)["p"] for a, b in zip(srm.n_t, srm.n_c)]
srm[srm.experiment_id == "E2_onboarding"]
""")
code("""
e2 = S["E2"]
pd.DataFrame({k: e2[k] for k in ("naive", "ios_only", "itt")}).T[["diff", "ci_low", "ci_high", "p"]]
""")
md("""
Assignment is a deterministic hash of the user id, so the intended group of every sign-up can be rebuilt (intent-to-treat), including
Android users whose exposure was never logged. Raw read ≈ +5.7 pts; honest read ≈ +3 pts.

### 5.4 Two-sided market: interference (E3 smart picks)
""")
code("""
m = run("11_interference_by_design.sql", con)
print(json.dumps({k: S["E3"][k] for k in ("cluster", "spillover_control_drop")}, indent=1))
print("user-split read:", {k: round(S["E3"]["naive"][k], 4) for k in ("rel", "rel_low", "rel_high", "p")})
m.groupby(["design", "variant"])[["users"]].sum()
""")
md("### 5.5 Five tests at once (E4): multiple-testing correction")
code("""
e4 = pd.read_csv(OUT / "p_e4.csv")
e4[["experiment", "rel", "p", "p_holm", "p_bh"]]
""")
md("### 5.6 Peeking (E5): daily reads vs a fixed horizon vs an O'Brien-Fleming boundary")
code("""
e5 = pd.read_csv(OUT / "p_e5_daily.csv")
print(e5.loc[e5.p < 0.05, ["day", "rel", "p"]])
print("final:", e5.iloc[-1][["day", "rel", "p"]].to_dict())
ab.peeking_fpr(n_per_day=600, days=28, p_base=0.57, n_sims=500)   # A/A simulations (500 here for speed; 2,000 in the report)
""")
md("### 5.7 CUPED (E6 ice-breakers): same decision with fewer users")
code("""
d6 = run("12_cuped_inputs.sql", con)
cu = ab.cuped(d6.y_messages, d6.x_pre_messages, d6.variant == "treatment")
print(f"theta = {cu['theta']:.3f}, rho = {cu['rho']:.3f}, variance reduction = {cu['var_reduction']:.1%}")
pd.DataFrame({"raw": cu["raw"], "CUPED": cu["adjusted"]}).T[["rel", "rel_low", "rel_high", "p"]]
""")

md("## 6. Predictive model: who cancels at the first renewal (SIMULATED)\nFeatures from the first 7 days of the subscription only (`sql/13`), 5-fold stratified CV.")
code("""print(json.dumps(S["churn"], indent=1)); pd.read_csv(OUT / "p_churn_by_matches.csv")""")
code("""pd.read_csv(OUT / "p_churn_coefs.csv").reindex(pd.read_csv(OUT / "p_churn_coefs.csv").coef_std.abs().sort_values(ascending=False).index).head(8)""")

md("## 7. Last step: compare with the hidden truth\nOpened only now, after every estimate above was written.")
code("""pd.read_csv(ROOT / "data" / "_hidden_truth.csv")""")


def main():
    utf8()
    nb = nbf.v4.new_notebook()
    nb["cells"] = cells
    nb["metadata"] = {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"}}
    NB.parent.mkdir(exist_ok=True)
    ExecutePreprocessor(timeout=600, kernel_name="python3").preprocess(nb, {"metadata": {"path": str(NB.parent)}})
    nbf.write(nb, NB)
    print(f"written and executed {NB.relative_to(ROOT)} ({len(cells)} cells)")


if __name__ == "__main__":
    main()

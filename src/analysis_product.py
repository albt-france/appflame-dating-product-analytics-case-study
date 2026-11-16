"""SIMULATED product analysis: KPIs, four growth opportunities -> hypotheses, six A/B tests, churn model.

Reads data/simulated/*.parquet through the SQL files in sql/, writes data/output/product_results.json and the
chart tables data/output/p_*.csv. The hidden truth (data/_hidden_truth.csv) is read only in the last step.
Usage:  python src/analysis_product.py
"""
import json

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import ab_stats as ab
from common import DATA, OUT, sim_con, utf8
from run_sql import run

R = {}


def save(df, name):
    df.to_csv(OUT / f"p_{name}.csv", index=False)
    return df


def clean(o):
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items() if k != "y_adj"}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if np.isnan(o) else round(float(o), 6)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.ndarray):
        return clean(o.tolist())
    if isinstance(o, (pd.Timestamp,)):
        return str(o.date())
    return o


# ----------------------------------------------------------------------------------------- KPIs
def kpis(con):
    k = con.sql("""
        with u as (select count(*) n from users),
        a as (select count(distinct user_id) n from events where event_name = 'activated'),
        p as (select count(distinct user_id) n, sum(revenue_usd) rev from subscriptions where paid_periods > 0),
        pm as (select sum(revenue_usd) / sum(least(paid_periods * period_days, 9999)) * 30 rpm from subscriptions where paid_periods > 0),
        m as (select sum(matches) matches, sum(messages_sent) msgs from daily_activity),
        c as (select count(distinct user_id) n from events where event_name = 'first_conversation')
        select u.n users, a.n / u.n activation, p.n / u.n payer_share, p.rev revenue, pm.rpm revenue_per_payer_month,
               m.matches, c.n / u.n conversation_share
        from u, a, p, pm, m, c""").df().iloc[0].to_dict()
    coh = save(run("02_cohort_retention.sql", con), "cohorts")
    w = coh["cohort_size"]
    for d in ("d1", "d7", "d14", "d30"):
        k[f"retention_{d}"] = float((coh[d] * w).sum() / w.sum())
    rev = save(run("05_revenue_per_user_payer.sql", con), "revenue_cohorts")
    k["arpu_30d"] = float(rev["revenue_30d"].sum() / rev["users"].sum())
    k["arppu_30d"] = float((rev["arppu_30d"] * rev["payer_share_30d"] * rev["users"]).sum() / (rev["payer_share_30d"] * rev["users"]).sum())
    save(run("14_product_pulse_daily.sql", con), "pulse_daily")
    save(run("03_activation_by_segment.sql", con), "activation_segments")
    save(run("04_paywall_conversion.sql", con), "paywall")
    R["kpis"] = k


# -------------------------------------------------------------------------------- opportunities
def opportunities(con):
    O = {}
    f = save(run("01_onboarding_funnel.sql", con), "funnel")
    # the pass rate of the row after the photo step = share who finished the photo step
    pr = f.pivot(index="step", columns="platform", values="pass_from_previous")
    photo_out = pr.loc["5_bio"]
    reach_photo = f[f["step"] == "4_photo_upload"].set_index("platform")["users"]
    months = 6
    lost = reach_photo["android"] * (photo_out["ios"] - photo_out["android"])
    # value of an onboarded user: revenue to date per onboarded user (all cohorts)
    v = con.sql("""select sum(coalesce(s.revenue_usd, 0)) / count(*) v from users u
                   join (select distinct user_id from events where event_name = 'onboarding_completed') o using (user_id)
                   left join subscriptions s using (user_id)""").fetchone()[0]
    O["photo"] = dict(pass_ios=photo_out["ios"], pass_android=photo_out["android"], android_reaching=reach_photo["android"],
                      extra_onboarded_per_month=lost / months, value_per_onboarded=v, revenue_per_month=lost / months * v,
                      hypothesis="If the Android photo step accepts any gallery format and lets users add a photo later, then "
                                 "onboarding completion on Android will rise toward iOS level, because 34% of Android users leave "
                                 "exactly at that step while iOS users pass it at 89%.",
                      metric="onboarding completion (Android)", guardrails="profiles with >= 1 photo after 7 days; report rate; likes received per profile",
                      n_per_arm=ab.sample_size_prop(0.53, 0.05))
    lb = save(run("06_like_balance.sql", con), "like_balance")
    z = lb[lb["likes_bucket"] == "0"].iloc[0]
    rest = lb[lb["likes_bucket"] != "0"]
    d1_rest = float((rest["return_d1"] * rest["users"]).sum() / rest["users"].sum())
    d0 = con.sql("""select likes_received from daily_activity where days_since_signup = 0
                    and user_id in (select user_id from events where event_name = 'onboarding_completed')""").df()["likes_received"].to_numpy()
    s = np.sort(d0)
    gini = 1 - 2 * np.sum(np.cumsum(s) / s.sum()) / len(s) + 1 / len(s)
    O["likes"] = dict(share_zero=z["share_of_users"], return_d1_zero=z["return_d1"], return_d1_rest=d1_rest,
                      top10_share=z["top10pct_share_of_likes"], gini_day0_likes=gini, share_side_a_in_zero=z["share_side_a"],
                      hypothesis="If every new profile is guaranteed a minimum exposure on day 0 (a fair-exposure slot in the "
                                 "card stack), then day-1 return will rise, because new users who receive no like on day 0 come "
                                 f"back half as often ({z['return_d1']:.0%} vs {d1_rest:.0%}).",
                      metric="day-1 return of new users", guardrails="likes received by existing users; match rate; reports",
                      design="two-sided: randomise by metro (cluster), see test E3", n_per_arm=ab.sample_size_prop(0.38, 0.04))
    ph = save(run("07_push_hour.sql", con), "push_hour")
    best = ph[ph["local_hour"].between(19, 21)]
    allr = (ph["open_rate"] * ph["pushes"]).sum() / ph["pushes"].sum()
    b = (best["open_rate"] * best["pushes"]).sum() / best["pushes"].sum()
    rb = (best["return_rate"] * best["pushes"]).sum() / best["pushes"].sum()
    ra = (ph["return_rate"] * ph["pushes"]).sum() / ph["pushes"].sum()
    O["push"] = dict(open_all=allr, open_19_21=b, return_all=ra, return_19_21=rb,
                     extra_returns_per_month=ph["pushes"].sum() / 6 * (rb - ra),
                     hypothesis="If re-engagement pushes are sent between 19:00 and 21:00 local time instead of a fixed spread "
                                f"over the day, then same-day return will rise from {ra:.1%} to about {rb:.1%}, because users "
                                "open dating apps in the evening.",
                     metric="same-day return after a push", guardrails="push opt-out rate; uninstalls", n_per_arm=ab.sample_size_prop(ra, 0.15))
    ch = save(run("08_channel_quality.sql", con), "channels")
    t = ch.set_index("channel")
    O["channel"] = dict(tiktok_roas=t.loc["tiktok", "roas_to_date"], tiktok_d30=t.loc["tiktok", "active_d28_32"],
                        organic_d30=t.loc["organic", "active_d28_32"], tiktok_payer=t.loc["tiktok", "payer_share"],
                        tiktok_cps=t.loc["tiktok", "cost_per_signup"], tiktok_rev=t.loc["tiktok", "revenue_per_signup"],
                        tiktok_spend_6m=float(con.sql("select sum(spend_usd) from ua_spend where channel='tiktok'").fetchone()[0]),
                        hypothesis="If 50% of the TikTok budget moves to Apple Search Ads and Meta, then revenue per dollar spent "
                                   "will rise, because TikTok sign-ups are cheap but stay half as long and pay 3x less "
                                   "(ROAS 0.79 after 90+ days vs 1.04-1.42).",
                        metric="revenue to date / spend (ROAS) at day 90", guardrails="total sign-ups; market balance (likes per new profile)",
                        design="geo holdout: cut TikTok in half of the metros for 6 weeks")
    R["opportunities"] = O


# ------------------------------------------------------------------------------------ E1 price
def e1(con):
    df = run("09_experiment_readout.sql", con)
    t, c = df[df["variant"] == "treatment"], df[df["variant"] == "control"]
    # power analysis BEFORE the test, on May-June sign-ups (same metric, no test running)
    base = con.sql("""
        with pay as (select s.user_id, s.first_payment_date + to_days(cast(k * s.period_days as integer)) paid_on,
                            s.price_usd - case when s.refunded and k = 0 then s.price_usd else 0 end amount
                     from subscriptions s, range(0, 60) t(k) where k < s.paid_periods)
        select u.user_id, coalesce(sum(p.amount) filter (where p.paid_on <= u.signup_date + interval 30 day), 0) rev_d30
        from users u left join pay p using (user_id)
        where u.signup_date between date '2026-05-01' and date '2026-06-30' group by u.user_id""").df()["rev_d30"]
    pre = dict(mean=base.mean(), sd=base.std(), conv=float((base > 0).mean()),
               n_per_arm_8pct=ab.sample_size_mean(base.mean(), base.std(), 0.08),
               n_per_arm_12pct=ab.sample_size_mean(base.mean(), base.std(), 0.12),
               n_per_arm_conv_10pct=ab.sample_size_prop(float((base > 0).mean()), -0.10),
               signups_per_day=float(con.sql("select count(*) / 61 from users where signup_date between date '2026-05-01' and date '2026-06-30'").fetchone()[0]))
    pre["days_needed_8pct"] = 2 * pre["n_per_arm_8pct"] / pre["signups_per_day"]
    pre["days_needed_12pct"] = 2 * pre["n_per_arm_12pct"] / pre["signups_per_day"]
    res = dict(pre=pre, conv_d30=ab.prop_test(t["paid_d30"].sum(), len(t), c["paid_d30"].sum(), len(c)),
               rev_d1=ab.mean_test(t["rev_d1"], c["rev_d1"]), rev_d7=ab.mean_test(t["rev_d7"], c["rev_d7"]),
               rev_d30=ab.mean_test(t["rev_d30"], c["rev_d30"]), mde_achieved=ab.mde_mean(c["rev_d30"].mean(), c["rev_d30"].std(), min(len(t), len(c))))
    # novelty: first-week read vs full test, and the lift by assignment week
    wk = df.assign(week=((pd.to_datetime(df["assigned_on"]) - pd.Timestamp("2026-07-01")).dt.days // 7) + 1)
    rows = []
    for w_, g in wk.groupby("week"):
        gt, gc = g[g["variant"] == "treatment"], g[g["variant"] == "control"]
        cv = ab.prop_test(gt["paid_d30"].sum(), len(gt), gc["paid_d30"].sum(), len(gc))
        rv = ab.mean_test(gt["rev_d30"], gc["rev_d30"])
        c1 = ab.prop_test(gt["paid_d1"].sum(), len(gt), gc["paid_d1"].sum(), len(gc))
        rows.append(dict(week=w_, users=len(g), conv_d1_rel=c1["rel"], conv_rel=cv["rel"], rev_d30_rel=rv["rel"], rev_d30_low=rv["rel_low"], rev_d30_high=rv["rel_high"]))
    save(pd.DataFrame(rows), "e1_weekly")
    w1 = wk[wk["week"] == 1]
    res["week1_conv"] = ab.prop_test(w1[w1.variant == "treatment"]["paid_d1"].sum(), (w1.variant == "treatment").sum(),
                                     w1[w1.variant == "control"]["paid_d1"].sum(), (w1.variant == "control").sum())
    res["week1_rev_d1"] = ab.mean_test(w1[w1.variant == "treatment"]["rev_d1"], w1[w1.variant == "control"]["rev_d1"])
    # guardrails: refunds, first renewal, day-28-32 activity
    g = con.sql("""
        select e.variant, avg(s.refunded::int) refund_rate,
               avg(case when s.paid_periods >= 2 then 1.0 when s.status = 'cancelled' then 0.0 end) renew1,
               count(s.user_id) subs
        from experiments e join subscriptions s using (user_id)
        where e.experiment_id = 'E1_paywall_price' and s.paid_periods >= 1 group by 1""").df().set_index("variant")
    act = con.sql("""select e.variant, avg((d.user_id is not null)::int) a from experiments e
                     left join (select distinct user_id from daily_activity where days_since_signup between 28 and 32) d using (user_id)
                     where e.experiment_id = 'E1_paywall_price' group by 1""").df().set_index("variant")["a"]
    res["guardrails"] = dict(refund_t=g.loc["treatment", "refund_rate"], refund_c=g.loc["control", "refund_rate"],
                             renew1_t=g.loc["treatment", "renew1"], renew1_c=g.loc["control", "renew1"],
                             active_d30_t=act["treatment"], active_d30_c=act["control"],
                             refund_test=ab.prop_test(g.loc["treatment", "refund_rate"] * g.loc["treatment", "subs"], g.loc["treatment", "subs"],
                                                      g.loc["control", "refund_rate"] * g.loc["control", "subs"], g.loc["control", "subs"]))
    res["srm"] = ab.srm_test(len(t), len(c))
    save(pd.DataFrame([dict(metric=m, **{k: res[m][k] for k in ("rel", "rel_low", "rel_high", "p")}) for m in ("conv_d30", "rev_d1", "rev_d7", "rev_d30")]), "e1_metrics")
    R["E1"] = res


# ------------------------------------------------------------------------------- E2 onboarding
def e2(con):
    srm = save(run("10_srm_check.sql", con), "srm")
    from scipy.stats import chi2
    srm["p"] = chi2.sf(srm["chi2"], 1)
    save(srm, "srm")
    d = con.sql("""
        select e.user_id, e.variant, u.platform,
               (o.user_id is not null)::int completed
        from experiments e join users u using (user_id)
        left join (select distinct user_id from events where event_name = 'onboarding_completed') o using (user_id)
        where e.experiment_id = 'E2_onboarding'""").df()

    def read(x):
        tt, cc = x[x.variant == "treatment"], x[x.variant == "control"]
        return ab.prop_test(tt["completed"].sum(), len(tt), cc["completed"].sum(), len(cc))
    res = dict(srm_all=ab.srm_test((d.variant == "treatment").sum(), (d.variant == "control").sum()),
               srm_android=ab.srm_test(((d.variant == "treatment") & (d.platform == "android")).sum(), ((d.variant == "control") & (d.platform == "android")).sum()),
               srm_ios=ab.srm_test(((d.variant == "treatment") & (d.platform == "ios")).sum(), ((d.variant == "control") & (d.platform == "ios")).sum()),
               naive=read(d), ios_only=read(d[d.platform == "ios"]))
    # intent-to-treat: assignment is a deterministic hash of user_id, so the intended variant of every sign-up
    # in the window can be rebuilt, including the Android users whose exposure was never logged
    from simulate import variant
    w = con.sql("""select u.user_id, u.platform, (o.user_id is not null)::int completed from users u
                   left join (select distinct user_id from events where event_name = 'onboarding_completed') o using (user_id)
                   where u.signup_date between date '2026-08-03' and date '2026-08-23'""").df()
    w["variant"] = variant(w["user_id"], "onboarding_v3")
    res["itt"] = read(w)
    res["itt_android"] = read(w[w.platform == "android"])
    res["missing_android_treatment"] = int(((w.variant == "treatment") & (w.platform == "android")).sum()
                                           - ((d.variant == "treatment") & (d.platform == "android")).sum())
    R["E2"] = res


# ------------------------------------------------------------------------------ E3 interference
def e3(con):
    m = save(run("11_interference_by_design.sql", con), "e3_metros")
    us = m[m["design"] == "user"]
    # user-split metros: user-level read (what a standard A/B tool would report)
    u = con.sql("""
        with a as (select user_id, variant, unit from experiments where experiment_id = 'E3_smart_picks')
        select a.user_id, a.variant, a.unit,
               coalesce(sum(d.matches) filter (where d.activity_date between date '2026-09-01' and date '2026-09-28'), 0) y,
               coalesce(sum(d.matches) filter (where d.activity_date between date '2026-08-04' and date '2026-08-31'), 0) x
        from a left join daily_activity d using (user_id) group by all""").df()
    uu = u[u.unit == "user"]
    naive = ab.mean_test(uu[uu.variant == "treatment"]["y"], uu[uu.variant == "control"]["y"])
    # cluster design: one observation per metro, outcome = test-period matches per user / pre-period matches per user
    cl = m[m["design"] == "metro"].copy()
    cl["ratio"] = cl["matches_per_user_test"] / cl["matches_per_user_pre"]
    ct, cc = cl[cl.variant == "treatment"], cl[cl.variant == "control"]
    from scipy import stats
    tt = stats.ttest_ind(ct["ratio"], cc["ratio"], equal_var=False)
    rel = ct["ratio"].mean() / cc["ratio"].mean() - 1
    se_rel = np.sqrt(ct["ratio"].var() / len(ct) + cc["ratio"].var() / len(cc)) / cc["ratio"].mean()
    dof = len(ct) + len(cc) - 2
    tc = stats.t.ppf(0.975, dof)
    # spill-over check: control users inside split metros vs control metros (same pre-period adjustment)
    us_c = us[us.variant == "control"]
    split_ctrl_ratio = (us_c["matches_per_user_test"] * us_c["users"]).sum() / (us_c["matches_per_user_pre"] * us_c["users"]).sum()
    cl_ctrl_ratio = (cc["matches_per_user_test"] * cc["users"]).sum() / (cc["matches_per_user_pre"] * cc["users"]).sum()
    R["E3"] = dict(naive=naive, cluster=dict(rel=rel, rel_low=rel - tc * se_rel, rel_high=rel + tc * se_rel, p=tt.pvalue,
                                             n_metros_t=len(ct), n_metros_c=len(cc)),
                   spillover_control_drop=split_ctrl_ratio / cl_ctrl_ratio - 1,
                   pre_balance=ab.mean_test(uu[uu.variant == "treatment"]["x"], uu[uu.variant == "control"]["x"]))


# ------------------------------------------------------------------------------ E4 multiple tests
def e4(con):
    d = con.sql("""
        with ret as (select distinct user_id from daily_activity where days_since_signup between 1 and 7)
        select e.experiment_id, e.variant, count(*) n, sum((r.user_id is not null)::int) x
        from experiments e left join ret r using (user_id)
        where e.experiment_id like 'E4%' group by 1, 2 order by 1, 2""").df()
    rows = []
    for ex, g in d.groupby("experiment_id"):
        g = g.set_index("variant")
        r = ab.prop_test(g.loc["treatment", "x"], g.loc["treatment", "n"], g.loc["control", "x"], g.loc["control", "n"])
        rows.append(dict(experiment=ex, rate_c=r["rate_c"], rate_t=r["rate_t"], rel=r["rel"], rel_low=r["rel_low"], rel_high=r["rel_high"], p=r["p"]))
    t = pd.DataFrame(rows)
    adj = ab.adjust_pvalues(t["p"])
    for k, v in adj.items():
        t[f"p_{k}"] = v
    save(t, "e4")
    R["E4"] = dict(table=t.to_dict("records"), fwer_5_tests=1 - 0.95 ** 5)


# ----------------------------------------------------------------------------------- E5 peeking
def e5(con):
    d = con.sql("""
        select e.user_id, e.variant, u.signup_date,
               (a.user_id is not null)::int y
        from experiments e join users u using (user_id)
        left join (select user_id from daily_activity where days_since_signup = 0 and likes_sent > 0) a using (user_id)
        where e.experiment_id = 'E5_profile_prompt'""").df()
    d["day"] = (pd.to_datetime(d["signup_date"]) - pd.Timestamp("2026-10-01")).dt.days + 1
    rows = []
    days = int(d["day"].max())
    bound = ab.obf_boundary(np.arange(1, days + 1) / days)
    for k in range(1, days + 1):
        x = d[d["day"] <= k]
        tt, cc = x[x.variant == "treatment"], x[x.variant == "control"]
        r = ab.prop_test(tt["y"].sum(), len(tt), cc["y"].sum(), len(cc))
        rows.append(dict(day=k, users=len(x), rel=r["rel"], rel_low=r["rel_low"], rel_high=r["rel_high"], z=r["z"], p=r["p"], obf_z=bound[k - 1]))
    t = save(pd.DataFrame(rows), "e5_daily")
    first_sig = t[t["p"] < 0.05]
    base = d[d.variant == "control"]["y"].mean()
    R["E5"] = dict(first_sig_day=int(first_sig["day"].min()) if len(first_sig) else None,
                   min_p=t["p"].min(), min_p_day=int(t.loc[t["p"].idxmin(), "day"]), final=rows[-1], days_significant=int((t["p"] < 0.05).sum()),
                   obf_crossed=bool((t["z"].abs() > t["obf_z"]).any()), base_rate=base, obf_c=float(bound[-1]),
                   aa=ab.peeking_fpr(n_per_day=int(len(d) / days / 2), days=days, p_base=base, n_sims=2000))


# --------------------------------------------------------------------------------------- E6 CUPED
def e6(con):
    d = run("12_cuped_inputs.sql", con)
    treat = (d["variant"] == "treatment").to_numpy()
    c = ab.cuped(d["y_messages"], d["x_pre_messages"], treat)
    sd_raw = d["y_messages"].std()
    sd_adj = np.std(c["y_adj"], ddof=1)
    m = d["y_messages"].mean()
    c["n_per_arm_raw_5pct"] = ab.sample_size_mean(m, sd_raw, 0.05)
    c["n_per_arm_cuped_5pct"] = ab.sample_size_mean(m, sd_adj, 0.05)
    c["n_users"] = len(d)
    # half the users, CUPED: does the conclusion hold?
    rng = np.random.default_rng(42)
    half = rng.random(len(d)) < 0.5
    ch = ab.cuped(d["y_messages"][half], d["x_pre_messages"][half], treat[half])
    c["half_sample_cuped"] = ch["adjusted"]
    c["half_sample_raw"] = ch["raw"]
    save(pd.DataFrame([dict(read=k, **{x: v[x] for x in ("rel", "rel_low", "rel_high", "p", "n_t", "n_c")})
                       for k, v in (("raw, all users", c["raw"]), ("CUPED, all users", c["adjusted"]),
                                    ("raw, half the users", ch["raw"]), ("CUPED, half the users", ch["adjusted"]))]), "e6")
    R["E6"] = c


# ------------------------------------------------------------------------------------ churn model
def churn(con):
    d = run("13_churn_features.sql", con)
    y = d["churned_first_period"].to_numpy()
    num = ["price_usd", "days_signup_to_sub", "active_days_7d", "matches_7d", "messages_7d", "likes_received_7d", "swipes_7d"]
    X = pd.get_dummies(d[num + ["plan", "trial", "country", "platform", "channel"]], columns=["plan", "country", "platform", "channel"],
                       drop_first=True, dtype=float)
    X["trial"] = X["trial"].astype(float)
    for col in ("matches_7d", "messages_7d", "likes_received_7d", "swipes_7d"):
        X[col] = np.log1p(X[col])
    cv = StratifiedKFold(5, shuffle=True, random_state=42)
    lr = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=1.0))
    gb = HistGradientBoostingClassifier(max_iter=250, learning_rate=0.05, max_leaf_nodes=15, random_state=42)
    p_lr = cross_val_predict(lr, X, y, cv=cv, method="predict_proba")[:, 1]
    p_gb = cross_val_predict(gb, X, y, cv=cv, method="predict_proba")[:, 1]
    lr.fit(X, y)
    coefs = pd.Series(lr[-1].coef_[0], index=X.columns).sort_values()
    gb.fit(X, y)
    pi = permutation_importance(gb, X, y, scoring="roc_auc", n_repeats=5, random_state=42)
    imp = pd.Series(pi.importances_mean, index=X.columns).sort_values(ascending=False)
    dec = pd.qcut(pd.Series(p_lr).rank(method="first"), 10, labels=False)
    lift = pd.DataFrame({"decile": 10 - dec, "y": y}).groupby("decile")["y"].mean().sort_index()
    save(pd.DataFrame({"feature": coefs.index, "coef_std": coefs.values}), "churn_coefs")
    save(pd.DataFrame({"feature": imp.index, "perm_importance_auc": imp.values}), "churn_importance")
    save(pd.DataFrame({"decile": lift.index, "churn_rate": lift.values}), "churn_deciles")
    bucket = pd.cut(d["matches_7d"], [-1, 0, 2, 5, 1e9], labels=["0", "1-2", "3-5", "6+"])
    by_m = d.groupby(bucket, observed=True)["churned_first_period"].agg(["mean", "size"]).reset_index()
    save(by_m.rename(columns={"matches_7d": "matches_7d_bucket", "mean": "churn_rate", "size": "subs"}), "churn_by_matches")
    R["churn"] = dict(n=len(d), base_rate=y.mean(), auc_lr=roc_auc_score(y, p_lr), auc_gb=roc_auc_score(y, p_gb),
                      brier_lr=brier_score_loss(y, p_lr), brier_gb=brier_score_loss(y, p_gb),
                      top_decile_rate=float(lift.loc[1]), bottom_decile_rate=float(lift.loc[10]),
                      top_coefs=coefs.abs().sort_values(ascending=False).head(6).index.tolist(),
                      churn_0_matches=float(by_m.iloc[0]["mean"]), churn_6plus=float(by_m.iloc[-1]["mean"]))


def truth():
    R["hidden_truth"] = pd.read_csv(DATA / "_hidden_truth.csv").to_dict("records")


def main():
    utf8()
    OUT.mkdir(parents=True, exist_ok=True)
    con = sim_con()
    for step in (kpis, opportunities, e1, e2, e3, e4, e5, e6, churn):
        step(con)
        print("done:", step.__name__)
    truth()          # only now, after every estimate is written
    (OUT / "product_results.json").write_text(json.dumps(clean(R), indent=1), encoding="utf-8")
    print("-> data/output/product_results.json")


if __name__ == "__main__":
    main()

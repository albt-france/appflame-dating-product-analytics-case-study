"""PUBLIC DATA analysis: market position of Hily and Taimi, review themes, and the speed-dating match model.

Inputs: data/public/*.csv (committed) and two local raw files (data/raw/reviews/*.parquet: review text is kept
local and never committed; data/raw/speed_dating/Speed Dating Data.csv). Outputs: data/output/pub_*.csv and
data/output/public_results.json (aggregates only: no review text, no reviewer name).
Usage:  python src/analysis_public.py
"""
import glob
import json
import re

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from common import OUT, PUB, RAW, utf8

R = {}
FOCUS = ["Hily", "Taimi"]


def save(df, name):
    df.to_csv(OUT / f"pub_{name}.csv", index=False)
    return df


# ------------------------------------------------------------------------------------- market
def market():
    lk = pd.read_csv(PUB / "appstore_lookup.csv")
    us = lk[lk["country"] == "us"].sort_values("rating_count", ascending=False)
    save(us[["app", "focus", "seller", "avg_rating", "rating_count", "current_version", "current_version_date", "first_release_date"]], "ratings_us")
    save(lk[lk["app"].isin(FOCUS)][["app", "country", "avg_rating", "rating_count"]], "ratings_focus_by_country")
    fx = pd.read_csv(PUB / "fx_ecb.csv").set_index("currency")["usd_per_unit"]
    iap = pd.read_csv(PUB / "appstore_iap_prices.csv")
    iap["price_usd"] = iap["price"] * iap["currency"].map(fx)
    # comparable items: one clearly named weekly or flagship subscription per app, same label in every storefront
    key = {"Hily": "1-week Hily Premium", "Taimi": "Taimi Gold Subscription"}
    rows = []
    for app, item in key.items():
        for cc, g in iap[(iap["app"] == app) & (iap["item"] == item)].groupby("country"):
            rows.append(dict(app=app, item=item, country=cc.upper(), price_local=g["price"].iloc[0], currency=g["currency"].iloc[0],
                             price_usd=round(g["price_usd"].iloc[0], 2), vat_included=cc in ("gb", "de", "fr")))
    px = save(pd.DataFrame(rows), "price_by_country")
    rng = iap[iap["country"] == "us"].groupby("app")["price_usd"].agg(["min", "median", "max", "size"]).reset_index()
    save(rng.rename(columns={"size": "items_listed"}), "price_range_us")
    us_hily = px[(px.app == "Hily") & (px.country == "US")]["price_usd"].iloc[0]
    eu = px[(px.app == "Hily") & px.country.isin(["GB", "DE", "FR"])]["price_usd"]
    R["market"] = dict(
        hily_rating_us=float(us.loc[us.app == "Hily", "avg_rating"].iloc[0]), hily_ratings_us=int(us.loc[us.app == "Hily", "rating_count"].iloc[0]),
        taimi_rating_us=float(us.loc[us.app == "Taimi", "avg_rating"].iloc[0]), taimi_ratings_us=int(us.loc[us.app == "Taimi", "rating_count"].iloc[0]),
        rank_ratings_hily=int((us["rating_count"] > us.loc[us.app == "Hily", "rating_count"].iloc[0]).sum() + 1),
        rank_ratings_taimi=int((us["rating_count"] > us.loc[us.app == "Taimi", "rating_count"].iloc[0]).sum() + 1),
        n_peers=len(us), hily_week_us=us_hily, hily_week_eu_avg_usd=float(eu.mean()), eu_premium=float(eu.mean() / us_hily - 1),
        fx_date=str(pd.read_csv(PUB / "fx_ecb.csv")["ecb_date"].iloc[0]),
        collected=str(lk["collected"].iloc[0]))
    # Google Trends
    t = pd.read_csv(PUB / "trends_weekly.csv", parse_dates=["date"])
    save(t, "trends_weekly")
    us_f = t[t["request"] == "US_focus"]
    yr = us_f.assign(year=us_f["date"].dt.year).groupby(["term", "year"])["interest"].mean().unstack()
    reg = pd.read_csv(PUB / "trends_by_country.csv")
    reg = reg[(reg["Hily"] + reg["Taimi"]) > 0]
    save(reg, "trends_by_country")
    R["trends"] = dict(hily_us_2026=float(yr.loc["Hily", 2026]), hily_us_2023=float(yr.loc["Hily", 2023]),
                       taimi_us_2026=float(yr.loc["Taimi", 2026]), taimi_us_2023=float(yr.loc["Taimi", 2023]),
                       grindr_us_2026=float(yr.loc["Grindr", 2026]), her_us_2026=float(yr.loc["HER app", 2026]),
                       note="Relative search interest (0-100) within one request; 'Taimi' and 'Hily' are also first names.")


# ------------------------------------------------------------------------------------- reviews
THEMES = {  # transparent keyword rules, checked by hand on a labelled sample (data/public/review_validation_labels.csv)
    "price": r"\bpay|paywall|subscri|expensive|overpriced|pricey|money|premium|\bgold\b|\bsilver\b|price|\bcost|\$\d|£\d|€\d|upgrade|credits?\b|coins?\b",
    "billing": r"charg|refund|cancel|billing|\bbilled|unsubscri|auto.?renew|took my money|stole",
    "fake_scam": r"\bfake|scam|\bbots?\b|catfish|spam|\bai\b|not real|real people|fraud",
    "matches_reach": r"no match|0 match|zero match|no likes|no one|nobody|no response|respond|distance|far away|\bkm\b|miles|province|location|same people|small (town|pool)|local",
    "account_ban": r"\bban|banned|blocked|suspend|locked out|disabled|deactivat|заблок|блок",
    "bugs": r"\bbug|crash|glitch|won.?t (let|load|work|open)|doesn.?t work|not working|error|freez|upload|keeps (logging|closing)|broken",
    "ads": r"\bads?\b|advert",
    "support": r"support|customer service|contact(ed)?|no reply|never (replied|answered)|appeal",
    "positive": r"\blove|great|best|amazing|awesome|fantastic|perfect|recommend|\bmet\b|found (my|a|some|someone)|works|good app|nice",
}
LABELS = {"price": "Paywall & price", "billing": "Billing & refunds", "fake_scam": "Fake profiles & scams",
          "matches_reach": "Few matches, distance, reach", "account_ban": "Bans & blocked accounts", "bugs": "Bugs & technical",
          "ads": "Ads", "support": "Support", "positive": "Positive experience"}


def classify(text, rating):
    t = text.lower()
    out = [k for k, rx in THEMES.items() if re.search(rx, t)]
    if "positive" in out and rating <= 2:
        out.remove("positive")                      # "best", "love" in a 1-star review are sarcasm or comparisons
    return out


def latest_reviews():
    """Most recent non-empty local snapshot (review text is never committed), or None."""
    for f in sorted(glob.glob(str(RAW / "reviews" / "*.parquet")), reverse=True):
        r = pd.read_parquet(f)
        if len(r):
            return r
    return None


def reviews():
    r = latest_reviews()
    if r is None:
        # fresh clone and an empty RSS feed: reuse the published aggregates (data/output/pub_review_*.csv)
        old = OUT / "public_results.json"
        R["reviews"] = json.loads(old.read_text(encoding="utf-8"))["reviews"]
        print("reviews: no local review text; published aggregates reused")
        return
    r["themes"] = [classify(f"{a} {b}", s) for a, b, s in zip(r["title"], r["text"], r["rating"])]
    # validation on the hand-labelled sample
    v = pd.read_csv(PUB / "review_validation_labels.csv", dtype={"review_id": str}).fillna("")
    v = v.merge(r[["review_id", "themes"]].astype({"review_id": str}), on="review_id")
    rows = []
    for k in THEMES:
        truth = v["manual_themes"].str.split(";").apply(lambda x: k in x)
        pred = v["themes"].apply(lambda x: k in x)
        tp, fp, fn = int((truth & pred).sum()), int((~truth & pred).sum()), int((truth & ~pred).sum())
        rows.append(dict(theme=LABELS[k], manual=int(truth.sum()), predicted=int(pred.sum()), tp=tp,
                         precision=tp / (tp + fp) if tp + fp else np.nan, recall=tp / (tp + fn) if tp + fn else np.nan))
    val = save(pd.DataFrame(rows), "review_validation")
    tp, pp, tt = val["tp"].sum(), val["predicted"].sum(), val["manual"].sum()
    # theme shares: last 12 months of written reviews
    rec = r[r["date"] >= "2025-11-15"].copy()
    rows = []
    for app, g in rec.groupby("app"):
        for k in THEMES:
            has = g["themes"].apply(lambda x: k in x)
            rows.append(dict(app=app, theme=LABELS[k], share=has.mean(), reviews=len(g), avg_rating_with_theme=g.loc[has, "rating"].mean()))
    th = save(pd.DataFrame(rows), "review_themes")
    stars = rec.groupby("app")["rating"].agg(["size", "mean", lambda x: (x <= 2).mean()]).reset_index()
    stars.columns = ["app", "reviews", "avg_rating", "share_1_2_stars"]
    save(stars, "review_summary")
    # release rhythm proxy: distinct app versions seen in reviews per 30 days (last 90 days of reviews)
    last = r[r["date"] >= "2026-08-17"]
    cad = last.groupby("app")["version"].nunique().rename("versions_seen_90d").reset_index()
    cad["versions_per_30d"] = cad["versions_seen_90d"] / 3
    save(cad, "release_rhythm")
    piv = th.pivot(index="theme", columns="app", values="share")
    R["reviews"] = dict(n_total=len(r), n_last12m=len(rec), n_validation=len(v), micro_precision=tp / pp, micro_recall=tp / tt,
                        hily_price=float(piv.loc["Paywall & price", "Hily"]), taimi_price=float(piv.loc["Paywall & price", "Taimi"]),
                        hily_fake=float(piv.loc["Fake profiles & scams", "Hily"]), taimi_fake=float(piv.loc["Fake profiles & scams", "Taimi"]),
                        hily_reach=float(piv.loc["Few matches, distance, reach", "Hily"]), taimi_ban=float(piv.loc["Bans & blocked accounts", "Taimi"]),
                        hily_ban=float(piv.loc["Bans & blocked accounts", "Hily"]),
                        peers_price=float(piv.loc["Paywall & price", ["Tinder", "Bumble", "Hinge"]].mean()),
                        peers_fake=float(piv.loc["Fake profiles & scams", ["Tinder", "Bumble", "Hinge"]].mean()),
                        hily_avg=float(stars.set_index("app").loc["Hily", "avg_rating"]), taimi_avg=float(stars.set_index("app").loc["Taimi", "avg_rating"]),
                        cadence=cad.set_index("app")["versions_per_30d"].round(1).to_dict())


# -------------------------------------------------------------------------------- speed dating
def speed_dating():
    d = pd.read_csv(RAW / "speed_dating" / "Speed Dating Data.csv", encoding="latin-1")
    # SENSITIVE variables are never used: race, race_o, samerace, imprace, imprelig, from, zipcode, income, gender
    d = d.dropna(subset=["pid"])
    d["pid"] = d["pid"].astype(int)
    # behavioural history = leave-one-out yes-rates inside the wave (an app's "likes given" / "likes received" rates)
    g_dec = d.groupby("iid")["dec"].agg(["sum", "count"])
    d["picky_loo"] = (d["iid"].map(g_dec["sum"]) - d["dec"]) / (d["iid"].map(g_dec["count"]) - 1)          # my yes-rate to others
    g_rec = d.groupby("iid")["dec_o"].agg(["sum", "count"])
    d["popular_loo"] = (d["iid"].map(g_rec["sum"]) - d["dec_o"]) / (d["iid"].map(g_rec["count"]) - 1)    # yes-rate I receive
    # partner's values, joined from the partner's own row
    part = d.set_index(["iid", "pid"])[["picky_loo", "popular_loo", "go_out", "date"]]
    part.index = part.index.set_names(["pid", "iid"])
    d = d.join(part.rename(columns=lambda c: c + "_p"), on=["pid", "iid"])
    # real-data like concentration: yeses received per person
    rec = d.groupby("iid")["dec_o"].sum().sort_values(ascending=False)
    top10 = rec.head(int(len(rec) * 0.10)).sum() / rec.sum()
    zero = (rec == 0).mean()
    pairs = d[d["iid"] < d["pid"]].copy()                     # one row per pair (each pair appears twice in the file)
    pairs["age_gap"] = (pairs["age"] - pairs["age_o"]).abs()
    pairs["same_field"] = (pairs["field_cd"] == d.set_index("iid")["field_cd"].groupby(level=0).first().reindex(pairs["pid"]).to_numpy()).astype(float)
    f_profile = ["int_corr", "age_gap", "same_field", "go_out", "go_out_p", "date", "date_p"]
    f_history = f_profile + ["picky_loo", "picky_loo_p", "popular_loo", "popular_loo_p"]
    f_ratings = f_history + ["attr", "fun", "shar", "intel", "sinc", "amb", "attr_o", "fun_o", "shar_o", "intel_o", "sinc_o", "amb_o"]
    pairs = pairs.dropna(subset=f_ratings + ["match"])
    y, groups = pairs["match"].to_numpy(), pairs["wave"].to_numpy()
    cv = GroupKFold(5)                                         # whole waves held out: no person in both train and test
    res, models = {}, {}
    for name, cols in (("profile", f_profile), ("profile_history", f_history), ("after_meeting", f_ratings)):
        X = pairs[cols]
        lr = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000))
        gb = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05, max_leaf_nodes=15, random_state=42)
        p_lr = cross_val_predict(lr, X, y, cv=cv, groups=groups, method="predict_proba")[:, 1]
        p_gb = cross_val_predict(gb, X, y, cv=cv, groups=groups, method="predict_proba")[:, 1]
        res[name] = dict(auc_lr=roc_auc_score(y, p_lr), auc_gb=roc_auc_score(y, p_gb), n_features=len(cols))
        models[name] = (lr.fit(X, y), gb.fit(X, y), X)
    lr, gb, X = models["after_meeting"]
    coefs = pd.Series(lr[-1].coef_[0], index=X.columns).sort_values(ascending=False)
    save(pd.DataFrame({"feature": coefs.index, "coef_std": coefs.values}), "sd_coefs")
    pi = permutation_importance(gb, X, y, scoring="roc_auc", n_repeats=5, random_state=42)
    save(pd.DataFrame({"feature": X.columns, "perm_importance_auc": pi.importances_mean}).sort_values("perm_importance_auc", ascending=False), "sd_importance")
    save(pd.DataFrame([dict(model=k, **v) for k, v in res.items()]), "sd_models")
    # match rate by perceived shared interests (both sides' rating) vs measured interest correlation
    pairs["shar_min"] = pairs[["shar", "shar_o"]].min(axis=1)
    by_shar = pairs.groupby(pd.cut(pairs["shar_min"], [-1, 3, 5, 7, 10], labels=["0-3", "4-5", "6-7", "8-10"]), observed=True)["match"].agg(["mean", "size"]).reset_index()
    save(by_shar.rename(columns={"shar_min": "lower_shared_interest_rating", "mean": "match_rate", "size": "pairs"}), "sd_by_shared")
    by_ic = pairs.groupby(pd.qcut(pairs["int_corr"], 4, labels=["Q1 low", "Q2", "Q3", "Q4 high"]), observed=True)["match"].mean()
    save(by_ic.reset_index().rename(columns={"match": "match_rate"}), "sd_by_intcorr")
    p_yes = d["dec"].mean()
    R["speed_dating"] = dict(rows=len(d), participants=int(d["iid"].nunique()), waves=int(d["wave"].nunique()), pairs=len(pairs),
                             yes_rate=p_yes, match_rate=float(d["match"].mean()), independent_match=p_yes ** 2,
                             corr_dec=float(np.corrcoef(d["dec"], d["dec_o"])[0, 1]),
                             top10_share_yes=float(top10), share_zero_yes=float(zero), models=res,
                             top_features=coefs.head(5).index.tolist(),
                             match_shared_high=float(by_shar.iloc[-1]["mean"]), match_shared_low=float(by_shar.iloc[0]["mean"]),
                             match_intcorr_q4=float(by_ic.iloc[-1]), match_intcorr_q1=float(by_ic.iloc[0]))


def main():
    utf8()
    OUT.mkdir(parents=True, exist_ok=True)
    market()
    reviews()
    speed_dating()
    (OUT / "public_results.json").write_text(json.dumps(R, indent=1, default=float), encoding="utf-8")
    print(json.dumps(R, indent=1, default=float)[:6000])


if __name__ == "__main__":
    main()

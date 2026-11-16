"""SIMULATED event log of a fictional dating app ("App H"), 6 months, ~200,000 sign-ups.

Nothing here is appflame, Hily or Taimi data. Orders of magnitude come from public sources
(data/public/industry_benchmarks.csv, data/public/appstore_iap_prices.csv); every assumption is in
data/ASSUMPTIONS.md. Seed 42: a re-run gives the same tables.

Tables written to data/simulated/ (ClickHouse-style: one wide event table + dimension tables):
  users           one row per sign-up (country, platform, channel, metro, neutral market side, age band)
  events          event log: onboarding steps, activation, first match/message, paywall, trial,
                  subscription, renewal, cancel, refund, boost purchase, report, experiment exposure
  daily_activity  one row per user x active day: sessions, swipes, likes sent/received, matches, messages
  notifications   re-engagement pushes (local send hour, opened, returned the same day)
  subscriptions   one row per subscription: plan, price, trial, paid periods, revenue, refund, status
  experiments     experiment assignments (experiment_id, user_id, variant, unit, cluster)
  ua_spend        daily paid acquisition spend by channel x country
and data/_hidden_truth.csv (the true effects, read only at the very end of the analysis).

Usage:  python src/simulate.py      (~1-2 minutes)
"""
import hashlib
from datetime import date, timedelta

import numpy as np
import pandas as pd

from common import DATA, SIM, utf8

SEED = 42
START, END = date(2026, 5, 1), date(2026, 10, 31)
N_DAYS = (END - START).days + 1                 # 184
N_USERS = 200_000
rng = np.random.default_rng(SEED)

COUNTRIES = {"US": 0.55, "GB": 0.20, "CA": 0.13, "AU": 0.12}
IOS_SHARE = {"US": 0.60, "GB": 0.52, "CA": 0.55, "AU": 0.56}
CHANNELS = ["organic", "apple_search_ads", "google_uac", "meta", "tiktok", "influencer"]
CH_RETENTION = {"organic": 1.10, "apple_search_ads": 1.05, "google_uac": 0.95, "meta": 0.92, "tiktok": 0.58, "influencer": 0.85}
CH_PAY = {"organic": 1.10, "apple_search_ads": 1.20, "google_uac": 0.90, "meta": 0.95, "tiktok": 0.55, "influencer": 0.80}
CPI = {"apple_search_ads": 4.6, "google_uac": 3.1, "meta": 4.0, "tiktok": 2.3, "influencer": 3.4}   # USD per sign-up
COUNTRY_PAY = {"US": 1.15, "GB": 0.95, "CA": 0.90, "AU": 0.90}
# price per plan in USD (control). Weekly price = Hily's public US App Store "1-week Hily Premium" ($14.99, 2026-11-15)
PLANS = {"weekly": (7, 14.99), "monthly": (30, 29.99), "quarterly": (90, 59.99)}
PLAN_MIX = [0.55, 0.35, 0.10]
PRICE_TEST_MULT = 19.99 / 14.99                  # E1 treatment: +33% on every plan
COUNTRY_PRICE = {"US": 1.00, "GB": 1.00, "CA": 0.80, "AU": 0.75}   # USD-equivalent index (see ASSUMPTIONS.md)
ONB_STEPS = ["basic_info", "birthday", "interests", "photo_upload", "bio", "location"]
PASS = {"ios": [0.93, 0.97, 0.94, 0.89, 0.95, 0.96], "android": [0.92, 0.97, 0.94, 0.66, 0.95, 0.95]}


def variant(user_ids, salt, share=0.5):
    """Deterministic assignment: hash(salt, user_id) -> 'control' / 'treatment' (what an assignment service does)."""
    h = np.array([int(hashlib.md5(f"{salt}:{u}".encode()).hexdigest()[:8], 16) for u in user_ids]) / 0xFFFFFFFF
    return np.where(h < share, "treatment", "control")


def day(d):
    return (d - START).days


# ------------------------------------------------------------------------------------------- users
def make_users():
    t = np.arange(N_DAYS)
    dow = np.array([(START + timedelta(int(i))).weekday() for i in t])
    weight = (1 + 0.0018 * t) * np.where(dow == 6, 1.22, np.where(dow == 5, 1.08, np.where(dow == 0, 1.05, 0.95)))
    weight *= 1 + 0.10 * np.sin((t - 60) / 184 * 2 * np.pi)          # mild summer bump
    sd = rng.choice(N_DAYS, N_USERS, p=weight / weight.sum())
    sd.sort()
    u = pd.DataFrame({"user_id": np.arange(1, N_USERS + 1), "signup_day": sd})
    u["country"] = rng.choice(list(COUNTRIES), N_USERS, p=list(COUNTRIES.values()))
    u["platform"] = np.where(rng.random(N_USERS) < u["country"].map(IOS_SHARE), "ios", "android")
    ch = rng.choice(CHANNELS, N_USERS, p=[0.35, 0.12, 0.15, 0.18, 0.12, 0.08])
    ch = np.where((ch == "apple_search_ads") & (u["platform"] == "android"), "google_uac", ch)
    ch = np.where((ch == "google_uac") & (u["platform"] == "ios"), "apple_search_ads", ch)
    u["channel"] = ch
    u["metro"] = u["country"] + "-" + pd.Series(rng.integers(1, 11, N_USERS)).astype(str).str.zfill(2)
    # neutral market side, used only for market balance (who receives more likes); no orientation, no gender label
    u["market_side"] = np.where(rng.random(N_USERS) < 0.62, "A", "B")
    u["age_band"] = rng.choice(["18-24", "25-34", "35-44", "45+"], N_USERS, p=[0.30, 0.40, 0.20, 0.10])
    secs = rng.integers(7 * 3600, 24 * 3600, N_USERS)
    u["signup_ts"] = pd.to_datetime([START + timedelta(int(d)) for d in sd]) + pd.to_timedelta(secs, unit="s")
    u["push_hour"] = 8 + (u["user_id"] * 2654435761 % 2**32) % 15          # scheduler: hash(user_id) -> 8h..22h local
    # latent traits (hidden: never exported)
    u["_appeal"] = rng.lognormal(0, 0.55, N_USERS)
    u["_engage"] = rng.lognormal(0, 0.45, N_USERS)
    return u


# -------------------------------------------------------------------------------- experiments plan
def assign(u):
    a = {}
    sd = u["signup_day"].to_numpy()
    e1 = (sd >= day(date(2026, 7, 1))) & (sd <= day(date(2026, 8, 25)))
    a["E1"] = np.where(e1, variant(u["user_id"], "paywall_price_v2"), None)
    e2 = (sd >= day(date(2026, 8, 3))) & (sd <= day(date(2026, 8, 23)))
    a["E2"] = np.where(e2, variant(u["user_id"], "onboarding_v3"), None)
    # E3: matching feature. Half of the metros randomise users, the other half randomise whole metros.
    metros = sorted(u["metro"].unique())
    mrng = np.random.default_rng(SEED + 3)
    design, metro_var = {}, {}
    for c in COUNTRIES:
        ms = [m for m in metros if m.startswith(c)]
        mrng.shuffle(ms)
        for m in ms[:5]:
            design[m] = "user_split"
        cl = ms[5:]
        for i, m in enumerate(cl):
            design[m], metro_var[m] = "cluster", ("treatment" if i < len(cl) // 2 + (mrng.random() < 0.5) else "control")
    u["_e3_design"] = u["metro"].map(design)
    uv = variant(u["user_id"], "smart_picks")
    a["E3"] = np.where(u["_e3_design"] == "user_split", uv, u["metro"].map(metro_var))
    a["E6"] = variant(u["user_id"], "icebreakers")
    return a, design


# ------------------------------------------------------------------------------------- onboarding
def onboarding(u, a):
    n = len(u)
    plat = u["platform"].to_numpy()
    treat2 = a["E2"] == "treatment"
    passed = np.ones(n, bool)
    last_step = np.full(n, 6)
    reached = np.zeros((n, 6), bool)
    for k in range(6):
        p = np.where(plat == "ios", PASS["ios"][k], PASS["android"][k])
        drop = 1 - p
        drop = np.where(treat2, drop * 0.90, drop)                    # E2 true effect: 10% fewer drop-offs per step
        reached[:, k] = passed
        ok = rng.random(n) < 1 - drop
        newly_lost = passed & ~ok
        last_step[newly_lost] = k
        passed &= ok
    u["_reached"] = list(reached)
    u["onboarded"] = passed
    u["_last_step"] = last_step
    return reached


# -------------------------------------------------------------------------------- daily activity
def activity(u, a):
    n = len(u)
    sd = u["signup_day"].to_numpy()
    span = N_DAYS - sd                                   # days observable incl. day 0
    idx = np.repeat(np.arange(n), span)
    dsince = np.arange(span.sum()) - np.repeat(np.cumsum(span) - span, span)
    cal = sd[idx] + dsince
    side_b = (u["market_side"] == "B").to_numpy()
    appeal, engage = u["_appeal"].to_numpy(), u["_engage"].to_numpy()
    lam_recv = 2.6 * appeal * np.where(side_b, 2.4, 0.55)              # likes received per active day
    # day-0 experience: likes received on the first day (new-profile boost x1.4)
    recv0 = rng.poisson(lam_recv * 1.4) * u["onboarded"].to_numpy()
    ch = u["channel"].map(CH_RETENTION).to_numpy()
    ph = u["push_hour"].to_numpy()
    hour_mult = np.select([(ph >= 19) & (ph <= 21), ph <= 10], [1.10, 0.94], 1.0)
    r1 = 0.40 * engage ** 0.6 * ch * np.where(recv0 == 0, 0.52, 1.0) * np.where(recv0 >= 5, 1.12, 1.0) * hour_mult
    r1 = np.where(u["onboarded"], r1, 0.04)
    r1 = np.clip(r1, 0, 0.92)
    p = np.where(dsince == 0, 1.0, r1[idx] * np.maximum(dsince, 1) ** -0.36)
    p = np.where((dsince == 0) & ~u["onboarded"].to_numpy()[idx], 1.0, p)
    active = rng.random(len(p)) < np.clip(p, 0, 0.95)
    ai, ad, ac = idx[active], dsince[active], cal[active]
    m = len(ai)
    sessions = 1 + rng.poisson(1.4 * engage[ai] ** 0.5)
    onb = u["onboarded"].to_numpy()[ai]
    swipes = np.where(onb, rng.poisson(30 * engage[ai] ** 0.7), 0)
    likes_sent = rng.binomial(swipes, np.where(side_b[ai], 0.22, 0.48))
    lr = np.where(ad == 0, recv0[ai], rng.poisson(lam_recv[ai]) * onb)
    # E3 (Sep 1-28): matching feature, two-sided. Total matches in a metro grow by tau*s; treated users get a
    # larger share (weight 1+beta) of a pool that control users share too -> user-level tests overstate the effect.
    e3win = (ac >= day(date(2026, 9, 1))) & (ac <= day(date(2026, 9, 28)))
    tau, beta = 0.04, 0.20
    design = u["_e3_design"].to_numpy()[ai]
    t3 = (a["E3"][ai] == "treatment")
    s = np.where(design == "user_split", 0.5, np.where(t3, 1.0, 0.0))
    w = np.where(t3, 1 + beta, 1.0)
    mult3 = np.where(e3win, (1 + tau * s) * w / (s * (1 + beta) + (1 - s)), 1.0)
    p_back = np.clip(0.30 * mult3, 0, 0.95)
    matches = rng.binomial(lr, p_back)
    # E6 (Oct 1-14): ice-breaker prompts, +5% messages for treated users
    e6win = (ac >= day(date(2026, 10, 1))) & (ac <= day(date(2026, 10, 14)))
    m6 = np.where(e6win & (a["E6"][ai] == "treatment"), 1.05, 1.0)
    messages = rng.poisson((2.2 * matches + 0.8 * (matches == 0) * (rng.random(m) < 0.25)) * engage[ai] ** 0.8 * m6
                           + 1.5 * engage[ai] * (rng.random(m) < 0.35))
    reports = rng.binomial(1, np.clip(0.004 + 0.0004 * matches, 0, 1))
    da = pd.DataFrame({"user_id": u["user_id"].to_numpy()[ai], "activity_date": pd.to_datetime(START) + pd.to_timedelta(ac, unit="D"),
                       "days_since_signup": ad.astype(np.int16), "sessions": sessions.astype(np.int16),
                       "swipes": swipes.astype(np.int16), "likes_sent": likes_sent.astype(np.int16),
                       "likes_received": lr.astype(np.int16), "matches": matches.astype(np.int16),
                       "messages_sent": messages.astype(np.int16), "reports": reports.astype(np.int8)})
    return da, recv0


# --------------------------------------------------------------------------------- notifications
def notifications(u, da):
    """One re-engagement push per inactive day, days 1-14 after sign-up, for onboarded users."""
    onb = u[u["onboarded"]][["user_id", "signup_day", "push_hour", "_engage"]]
    rows = np.repeat(onb.index.to_numpy(), 14)
    d = np.tile(np.arange(1, 15), len(onb))
    cal = onb["signup_day"].to_numpy().repeat(14) + d
    keep = cal < N_DAYS
    rows, d, cal = rows[keep], d[keep], cal[keep]
    uid = u.loc[rows, "user_id"].to_numpy()
    act = set(zip(da["user_id"].to_numpy(), da["days_since_signup"].to_numpy()))
    inactive = np.array([(a_, b_) not in act for a_, b_ in zip(uid, d)])
    rows, d, cal, uid = rows[inactive], d[inactive], cal[inactive], uid[inactive]
    ph = u.loc[rows, "push_hour"].to_numpy()
    base = np.select([(ph >= 19) & (ph <= 21), (ph >= 12) & (ph <= 14), ph <= 10], [0.085, 0.060, 0.042], 0.052)
    opened = rng.random(len(rows)) < base * u.loc[rows, "_engage"].to_numpy() ** 0.5
    returned = opened & (rng.random(len(rows)) < 0.55)
    ts = pd.to_datetime(START) + pd.to_timedelta(cal, unit="D") + pd.to_timedelta(ph, unit="h")
    return pd.DataFrame({"user_id": uid, "sent_at_local": ts, "local_hour": ph.astype(np.int8),
                         "days_since_signup": d.astype(np.int16), "opened": opened, "returned_same_day": returned})


# --------------------------------------------------------------------------------- monetisation
def monetisation(u, a, da):
    uix = pd.Series(np.arange(len(u)), index=u["user_id"])
    ui = uix[da["user_id"]].to_numpy()
    d0 = da["days_since_signup"].to_numpy() == 0
    heavy = da["swipes"].to_numpy() > 40
    view = rng.random(len(da)) < np.where(d0 & u["onboarded"].to_numpy()[ui], 0.70, np.where(heavy, 0.22, 0.06))
    pv = da.loc[view, ["user_id", "activity_date", "days_since_signup"]].copy()
    pui = uix[pv["user_id"]].to_numpy()
    cal = ((pv["activity_date"] - pd.Timestamp(START)).dt.days).to_numpy()
    e1 = a["E1"][pui]
    treat = e1 == "treatment"
    first_week = (cal - u["signup_day"].to_numpy()[pui] <= 7) & (cal < day(date(2026, 7, 8)))  # novelty: first test week
    p = 0.046 * u["_engage"].to_numpy()[pui] ** 0.7 * u["channel"].map(CH_PAY).to_numpy()[pui] \
        * u["country"].map(COUNTRY_PAY).to_numpy()[pui] * np.where(pv["days_since_signup"].to_numpy() == 0, 1.3, 1.0)
    p = np.where(treat, p * 0.87 * np.where(first_week, 1.30, 1.0), p)   # E1: -13% conversion; novelty x1.3 in week 1
    conv = rng.random(len(pv)) < np.clip(p, 0, 0.9)
    pv["converted"] = conv
    first = pv[conv].drop_duplicates("user_id")
    fu = uix[first["user_id"]].to_numpy()
    nsub = len(first)
    plan = rng.choice(list(PLANS), nsub, p=PLAN_MIX)
    trial = (plan == "weekly") & (rng.random(nsub) < 0.30)
    period = np.array([PLANS[p_][0] for p_ in plan])
    price = np.array([PLANS[p_][1] for p_ in plan]) * u["country"].map(COUNTRY_PRICE).to_numpy()[fu]
    t1 = a["E1"][fu] == "treatment"
    price = np.round(np.where(t1, price * PRICE_TEST_MULT, price), 2)
    start = first["activity_date"].to_numpy()
    start_day = ((first["activity_date"] - pd.Timestamp(START)).dt.days).to_numpy()
    # engagement in the 7 days after subscribing -> renewal (signal used by the churn model)
    da7 = da.merge(first[["user_id", "activity_date"]].rename(columns={"activity_date": "sub_date"}), on="user_id")
    da7 = da7[(da7["activity_date"] >= da7["sub_date"]) & (da7["activity_date"] < da7["sub_date"] + pd.Timedelta(days=7))]
    g = da7.groupby("user_id").agg(m7=("matches", "sum"), a7=("activity_date", "count"), msg7=("messages_sent", "sum"))
    g = g.reindex(first["user_id"]).fillna(0)
    m7, a7 = g["m7"].to_numpy(), g["a7"].to_numpy()
    logit = -0.35 + 0.55 * np.log1p(m7) + 0.18 * a7 + np.select([plan == "monthly", plan == "quarterly"], [0.35, 0.10], 0) \
        - 0.6 * trial + np.where(t1, -0.15, 0) + rng.normal(0, 0.6, nsub)
    p_renew1 = 1 / (1 + np.exp(-logit))
    p_renew_next = np.clip(p_renew1 + 0.12, 0, 0.93)
    trial_conv = np.where(trial, rng.random(nsub) < 0.52, True)
    pay_start = start_day + np.where(trial, 3, 0)
    # number of paid periods: first payment then renewals until a cancel (geometric), censored at END
    renew1 = rng.random(nsub) < p_renew1
    extra = rng.geometric(1 - p_renew_next) - 1
    periods_wanted = np.where(trial_conv, 1 + np.where(renew1, 1 + extra, 0), 0)
    max_periods = np.floor((N_DAYS - 1 - pay_start) / period).astype(int) + 1
    max_periods = np.where(pay_start <= N_DAYS - 1, max_periods, 0)
    paid = np.minimum(periods_wanted, max_periods)
    censored = periods_wanted > max_periods
    refunded = (paid >= 1) & (rng.random(nsub) < np.where(t1, 0.045, 0.030))
    revenue = np.round(paid * price - refunded * price, 2)
    end_day = np.where(trial_conv, pay_start + paid * period, start_day + 3)
    subs = pd.DataFrame({"subscription_id": np.arange(1, nsub + 1), "user_id": first["user_id"].to_numpy(), "plan": plan,
                         "period_days": period, "price_usd": price, "trial": trial, "trial_converted": np.where(trial, trial_conv, None),
                         "started_at": start, "first_payment_date": pd.to_datetime(START) + pd.to_timedelta(pay_start, unit="D"),
                         "paid_periods": paid, "renewals": np.maximum(paid - 1, 0), "refunded": refunded,
                         "revenue_usd": revenue,
                         "status": np.where(censored, "active", "cancelled"),
                         "ended_at": pd.Series(pd.to_datetime(START) + pd.to_timedelta(np.minimum(end_day, N_DAYS), unit="D")).where(~censored)})
    # boosts (consumables), bought by a few active users
    boost = da[(rng.random(len(da)) < 0.0035 * np.clip(da["swipes"].to_numpy() / 30, 0.2, 3))][["user_id", "activity_date"]].copy()
    boost["price_usd"] = rng.choice([5.99, 9.99], len(boost), p=[0.6, 0.4])
    return pv, subs, boost


# ------------------------------------------------------------------------------------ event log
def events(u, a, reached, da, pv, subs, boost):
    ev = []
    base = u["signup_ts"].to_numpy()
    uid = u["user_id"].to_numpy()
    ev.append(pd.DataFrame({"user_id": uid, "event_time": base, "event_name": "signup", "prop": u["channel"].to_numpy()}))
    for k, step in enumerate(ONB_STEPS):
        r = reached[:, k]
        ev.append(pd.DataFrame({"user_id": uid[r], "event_time": base[r] + np.timedelta64(30 * (k + 1), "s"),
                                "event_name": "onboarding_step", "prop": f"{k + 1}_{step}"}))
    o = u["onboarded"].to_numpy()
    ev.append(pd.DataFrame({"user_id": uid[o], "event_time": base[o] + np.timedelta64(200, "s"), "event_name": "onboarding_completed", "prop": None}))
    # profile completed (bio + 3 photos) for part of onboarded users
    pc = o & (rng.random(len(u)) < 0.62)
    ev.append(pd.DataFrame({"user_id": uid[pc], "event_time": base[pc] + np.timedelta64(900, "s"), "event_name": "profile_completed", "prop": None}))
    first_like = da[da["likes_sent"] > 0].drop_duplicates("user_id")
    fl = first_like[first_like["days_since_signup"] == 0]
    ev.append(pd.DataFrame({"user_id": fl["user_id"], "event_time": fl["activity_date"] + pd.Timedelta(hours=21), "event_name": "activated", "prop": None}))
    for col, name in (("matches", "first_match"), ("messages_sent", "first_message")):
        f = da[da[col] > 0].drop_duplicates("user_id")
        ev.append(pd.DataFrame({"user_id": f["user_id"], "event_time": f["activity_date"] + pd.Timedelta(hours=22), "event_name": name, "prop": None}))
    conv = da[(da["matches"] > 0) & (da["messages_sent"] >= 4)].drop_duplicates("user_id")
    ev.append(pd.DataFrame({"user_id": conv["user_id"], "event_time": conv["activity_date"] + pd.Timedelta(hours=23), "event_name": "first_conversation", "prop": None}))
    ev.append(pd.DataFrame({"user_id": pv["user_id"], "event_time": pv["activity_date"] + pd.Timedelta(hours=20), "event_name": "paywall_view", "prop": None}))
    t = subs[subs["trial"]]
    ev.append(pd.DataFrame({"user_id": t["user_id"], "event_time": t["started_at"] + pd.Timedelta(hours=20, minutes=1), "event_name": "trial_start", "prop": t["plan"]}))
    paid = subs[subs["paid_periods"] > 0]
    ev.append(pd.DataFrame({"user_id": paid["user_id"], "event_time": paid["first_payment_date"] + pd.Timedelta(hours=20, minutes=2),
                            "event_name": "subscription_start", "prop": paid["plan"]}))
    rr = paid.loc[paid.index.repeat(paid["renewals"])].copy()
    k = rr.groupby(level=0).cumcount() + 1
    rr["t"] = rr["first_payment_date"] + pd.to_timedelta(k * rr["period_days"], unit="D") + pd.Timedelta(hours=20, minutes=3)
    ev.append(pd.DataFrame({"user_id": rr["user_id"], "event_time": rr["t"], "event_name": "renewal", "prop": rr["plan"]}))
    c = subs[subs["status"] == "cancelled"]
    ev.append(pd.DataFrame({"user_id": c["user_id"], "event_time": c["ended_at"], "event_name": "cancel", "prop": c["plan"]}))
    rf = subs[subs["refunded"]]
    ev.append(pd.DataFrame({"user_id": rf["user_id"], "event_time": rf["first_payment_date"] + pd.Timedelta(days=2), "event_name": "refund", "prop": rf["plan"]}))
    ev.append(pd.DataFrame({"user_id": boost["user_id"], "event_time": boost["activity_date"] + pd.Timedelta(hours=21, minutes=30),
                            "event_name": "boost_purchase", "prop": boost["price_usd"].astype(str)}))
    rp = da[da["reports"] > 0]
    ev.append(pd.DataFrame({"user_id": rp["user_id"], "event_time": rp["activity_date"] + pd.Timedelta(hours=22, minutes=30), "event_name": "report_sent", "prop": None}))
    out = pd.concat(ev, ignore_index=True)
    out = out[out["event_time"] < pd.Timestamp(END) + pd.Timedelta(days=1)]
    return out.sort_values(["event_time", "user_id"]).reset_index(drop=True)


# ----------------------------------------------------------------------------------- experiments
def pick_seed(test_fn, cands=range(1, 400)):
    for s in cands:
        if test_fn(s):
            return s
    raise RuntimeError("no seed found")


def experiments(u, a, design, da, subs):
    rows = []
    sd = u["signup_day"].to_numpy()
    uid = u["user_id"].to_numpy()
    # E1 paywall price: all sign-ups 1 Jul - 25 Aug
    m = a["E1"] != None  # noqa: E711
    rows.append(pd.DataFrame({"experiment_id": "E1_paywall_price", "user_id": uid[m], "variant": a["E1"][m], "unit": "user", "cluster": None,
                              "assigned_at": u["signup_ts"].to_numpy()[m]}))
    # E2 onboarding: exposure logged at step 1, except Android treatment where a bug logs it at step 3
    m = a["E2"] != None  # noqa: E711
    reached3 = np.array([r[2] for r in u["_reached"]])
    lost = (a["E2"] == "treatment") & (u["platform"].to_numpy() == "android") & ~reached3
    m2 = m & ~lost
    rows.append(pd.DataFrame({"experiment_id": "E2_onboarding", "user_id": uid[m2], "variant": a["E2"][m2], "unit": "user", "cluster": None,
                              "assigned_at": u["signup_ts"].to_numpy()[m2]}))
    # E3 matching feature: users active during the test window (1-28 Sep), signed up before 1 Sep
    w = da[(da["activity_date"] >= "2026-09-01") & (da["activity_date"] <= "2026-09-28")]["user_id"].unique()
    w = w[sd[w - 1] < day(date(2026, 9, 1))]
    metro = u["metro"].to_numpy()[w - 1]
    rows.append(pd.DataFrame({"experiment_id": "E3_smart_picks", "user_id": w, "variant": a["E3"][w - 1],
                              "unit": np.where(pd.Series(metro).map(design) == "user_split", "user", "metro"), "cluster": metro,
                              "assigned_at": pd.Timestamp("2026-09-01")}))
    # E6 ice-breakers: users active 17-30 Sep, signed up before 17 Sep (they have a pre-period)
    w6 = da[(da["activity_date"] >= "2026-09-17") & (da["activity_date"] <= "2026-09-30")]["user_id"].unique()
    w6 = w6[sd[w6 - 1] < day(date(2026, 9, 17))]
    rows.append(pd.DataFrame({"experiment_id": "E6_icebreakers", "user_id": w6, "variant": a["E6"][w6 - 1], "unit": "user", "cluster": None,
                              "assigned_at": pd.Timestamp("2026-10-01")}))
    # E4: five UI tests at once on September sign-ups, none has a real effect; metric = return within days 1-7.
    from scipy.stats import norm
    sep = (sd >= day(date(2026, 9, 1))) & (sd <= day(date(2026, 9, 24)))
    ids4 = uid[sep]
    ret = da[(da["days_since_signup"] >= 1) & (da["days_since_signup"] <= 7)]["user_id"].unique()
    y4 = np.isin(ids4, ret).astype(float)

    def zp(y, t, signed=False):
        a1, b1 = y[t].mean(), y[~t].mean()
        se = np.sqrt(a1 * (1 - a1) / t.sum() + b1 * (1 - b1) / (~t).sum())
        p = 2 * norm.sf(abs((a1 - b1) / se))
        return (p, a1 > b1) if signed else p

    def ok4(s):
        r = np.random.default_rng(1000 + s)
        res = [zp(y4, r.random(len(ids4)) < 0.5, signed=True) for _ in range(5)]
        sig = [up for p, up in res if p < 0.05]
        return len(sig) == 1 and sig[0] and min(p for p, _ in res) > 0.012

    s4 = pick_seed(ok4)
    r4 = np.random.default_rng(1000 + s4)
    names = ["E4a_badge_color", "E4b_profile_tips", "E4c_dark_paywall", "E4d_swipe_hint", "E4e_new_icons"]
    for nm in names:
        t = r4.random(len(ids4)) < 0.5
        rows.append(pd.DataFrame({"experiment_id": nm, "user_id": ids4, "variant": np.where(t, "treatment", "control"), "unit": "user",
                                  "cluster": None, "assigned_at": u["signup_ts"].to_numpy()[sep]}))
    # E5: "profile prompt" test, no real effect, read every day for 28 days; metric = activation (like sent on day 0)
    oct_ = (sd >= day(date(2026, 10, 1))) & (sd <= day(date(2026, 10, 28)))
    ids5, sd5 = uid[oct_], sd[oct_]
    act = da[(da["days_since_signup"] == 0) & (da["likes_sent"] > 0)]["user_id"].unique()
    y5 = np.isin(ids5, act).astype(float)

    def ok5(s):
        t = np.random.default_rng(2000 + s).random(len(ids5)) < 0.5
        ps = []
        for dd in range(3, 29):
            mm = sd5 < day(date(2026, 10, 1)) + dd
            ps.append(zp(y5[mm], t[mm]))
        early = min(ps[:10])
        return early < 0.03 and ps[-1] > 0.30 and sum(p < 0.05 for p in ps) <= 6

    s5 = pick_seed(ok5)
    t5 = np.random.default_rng(2000 + s5).random(len(ids5)) < 0.5
    rows.append(pd.DataFrame({"experiment_id": "E5_profile_prompt", "user_id": ids5, "variant": np.where(t5, "treatment", "control"), "unit": "user",
                              "cluster": None, "assigned_at": u["signup_ts"].to_numpy()[oct_]}))
    ex = pd.concat(rows, ignore_index=True)
    return ex, {"E4_assignment_seed": s4, "E5_assignment_seed": s5}


def ua_spend(u):
    paid = u[u["channel"] != "organic"].copy()
    paid["date"] = pd.to_datetime(START) + pd.to_timedelta(paid["signup_day"], unit="D")
    g = paid.groupby(["date", "channel", "country"]).size().rename("signups").reset_index()
    noise = rng.normal(1, 0.08, len(g))
    g["spend_usd"] = np.round(g["signups"] * g["channel"].map(CPI) * g["country"].map({"US": 1.15, "GB": 0.95, "CA": 0.85, "AU": 0.85}) * noise, 2)
    return g[["date", "channel", "country", "spend_usd"]]


def main():
    utf8()
    SIM.mkdir(parents=True, exist_ok=True)
    u = make_users()
    a, design = assign(u)
    reached = onboarding(u, a)
    da, recv0 = activity(u, a)
    notif = notifications(u, da)
    pv, subs, boost = monetisation(u, a, da)
    ev = events(u, a, reached, da, pv, subs, boost)
    ex, seeds = experiments(u, a, design, da, subs)
    spend = ua_spend(u)
    users = u[["user_id", "signup_ts", "country", "platform", "channel", "metro", "market_side", "age_band", "push_hour"]].copy()
    users["signup_date"] = users["signup_ts"].dt.normalize()
    for name, df in (("users", users), ("events", ev), ("daily_activity", da), ("notifications", notif),
                     ("subscriptions", subs), ("experiments", ex), ("ua_spend", spend)):
        df.to_parquet(SIM / f"{name}.parquet", index=False)
        print(f"{name:15s} {len(df):>10,} rows")
    truth = pd.DataFrame([
        ("E1_paywall_price", "conversion to paid (per paywall view)", "-13% relative; x1.30 extra for treatment in the first test week (novelty)"),
        ("E1_paywall_price", "price", "+33% on every plan ($14.99 -> $19.99 weekly)"),
        ("E1_paywall_price", "first renewal", "logit -0.15 (slightly fewer renewals); refunds 4.5% vs 3.0%"),
        ("E2_onboarding", "drop-off per onboarding step", "-10% relative (small real gain); Android treatment exposure logged only from step 3 (bug -> SRM)"),
        ("E3_smart_picks", "matches, whole-market effect", "+4% when every user is treated (tau = 0.04); treated users take a 1.2x share of a pool shared with control"),
        ("E4a-e", "return within 7 days", f"no effect in any of the five tests (assignment seed {seeds['E4_assignment_seed']} chosen so exactly one is p < 0.05)"),
        ("E5_profile_prompt", "activation", f"no effect (assignment seed {seeds['E5_assignment_seed']} chosen so an early daily read crosses p < 0.05)"),
        ("E6_icebreakers", "messages sent, 1-14 Oct", "+5% for treated users"),
        ("opportunity", "Android photo-upload step", "pass rate 0.66 vs 0.89 on iOS"),
        ("opportunity", "no like received on day 0", "day-1 return probability x0.52"),
        ("opportunity", "push hour 19-21h", "open rate ~0.085 vs ~0.05; return probability x1.10"),
        ("opportunity", "tiktok cohort", "retention x0.58, payment x0.55 vs reference"),
    ], columns=["item", "metric", "true_effect"])
    truth.to_csv(DATA / "_hidden_truth.csv", index=False)
    print("hidden truth -> data/_hidden_truth.csv", seeds)


if __name__ == "__main__":
    main()

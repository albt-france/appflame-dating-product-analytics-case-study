"""Tidy extracts for the dashboards (Tableau and HTML fallback): CSV + .hyper (Tableau Public only saves
workbooks built on extracts) + schemas.json. Run after analysis_product.py and analysis_public.py.

    python src/export_tableau.py      -> data/output/tableau/*.csv, *.hyper, schemas.json
"""
import json

import duckdb
import pandas as pd

from common import OUT, PUB, sim_con, utf8

TAB = OUT / "tableau"

SIM_QUERIES = {
    # 1 Product pulse: one row per day x country x platform
    "pulse": """
        with days as (select unnest(generate_series(date '2026-05-01', date '2026-10-31', interval 1 day))::date d),
        seg as (select distinct country, platform from users),
        grid as (select d, country, platform from days, seg),
        s as (select signup_date::date d, country, platform, count(*) signups from users group by all),
        a as (select a.activity_date::date d, u.country, u.platform, count(*) dau, sum(matches) matches, sum(messages_sent) messages
              from daily_activity a join users u using (user_id) group by all),
        e as (select e.event_time::date d, u.country, u.platform,
                     count(*) filter (where event_name = 'activated') activated,
                     count(*) filter (where event_name = 'first_conversation') new_conversations,
                     count(*) filter (where event_name = 'subscription_start') new_payers
              from events e join users u using (user_id) group by all),
        r as (select (s.first_payment_date + to_days(cast(k * s.period_days as integer)))::date d, u.country, u.platform,
                     sum(s.price_usd - case when s.refunded and k = 0 then s.price_usd else 0 end) revenue_usd
              from subscriptions s join users u using (user_id), range(0, 60) t(k) where k < s.paid_periods group by all)
        select g.d as date, g.country, g.platform, coalesce(signups, 0) signups, coalesce(activated, 0) activated,
               coalesce(dau, 0) dau, coalesce(matches, 0) matches, coalesce(messages, 0) messages,
               coalesce(new_conversations, 0) new_conversations, coalesce(new_payers, 0) new_payers,
               round(coalesce(revenue_usd, 0), 2) revenue_usd
        from grid g left join s using (d, country, platform) left join a using (d, country, platform)
        left join e using (d, country, platform) left join r using (d, country, platform)
        order by 1, 2, 3""",
    # 2 Funnel: users reaching each stage, by segment (long format)
    "funnel": """
        with stages as (
            select user_id, prop as stage from events where event_name = 'onboarding_step'
            union all select user_id, '7_onboarding_completed' from events where event_name = 'onboarding_completed'
            union all select user_id, '8_activated' from events where event_name = 'activated'
            union all select user_id, '9_first_match' from events where event_name = 'first_match'
            union all select user_id, '10_first_conversation' from events where event_name = 'first_conversation'
            union all select distinct user_id, '11_paid' from events where event_name = 'subscription_start')
        select u.country, u.platform, u.channel, s.stage, cast(split_part(s.stage, '_', 1) as integer) stage_order,
               count(distinct s.user_id) users
        from stages s join users u using (user_id) group by all order by 1, 2, 3, 5""",
    # 3 Retention curves: active users by days since sign-up, monthly cohorts and segments
    "retention": """
        with c as (select user_id, date_trunc('month', signup_date)::date cohort_month, country, platform, channel from users),
        size as (select cohort_month, country, platform, channel, count(*) cohort_size from c group by all),
        act as (select c.cohort_month, c.country, c.platform, c.channel, a.days_since_signup as day_since_signup, count(*) active_users
                from daily_activity a join c using (user_id) where a.days_since_signup <= 60 group by all)
        select a.*, s.cohort_size,
               (date '2026-10-31' - (a.cohort_month + interval 1 month - interval 1 day)::date) >= a.day_since_signup as fully_observed
        from act a join size s using (cohort_month, country, platform, channel) order by 1, 2, 3, 4, 5""",
}


def tableau_type(duck_type: str) -> str:
    t = duck_type.upper()
    if t == "DATE":
        return "date"
    if t.startswith("TIMESTAMP"):
        return "datetime"
    if t in ("BIGINT", "INTEGER", "HUGEINT", "SMALLINT", "TINYINT", "UBIGINT"):
        return "integer"
    if t in ("DOUBLE", "FLOAT", "REAL") or t.startswith("DECIMAL"):
        return "real"
    if t == "BOOLEAN":
        return "boolean"
    return "string"


def write_hyper(csv_path, hyper_path, schema):
    """Write a CSV into a .hyper extract, table "Extract"."Extract" (the name Tableau expects)."""
    from tableauhyperapi import (Connection, CreateMode, HyperProcess, SqlType, TableDefinition, TableName, Telemetry,
                                 escape_string_literal)
    sql_type = {"date": SqlType.date(), "datetime": SqlType.timestamp(), "integer": SqlType.big_int(),
                "real": SqlType.double(), "boolean": SqlType.bool(), "string": SqlType.text()}
    table = TableDefinition(TableName("Extract", "Extract"), [TableDefinition.Column(c, sql_type[t]) for c, t in schema])
    with HyperProcess(telemetry=Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as hyper:
        with Connection(hyper.endpoint, str(hyper_path), CreateMode.CREATE_AND_REPLACE) as conn:
            conn.catalog.create_schema("Extract")
            conn.catalog.create_table(table)
            conn.execute_command(f"COPY {table.table_name} FROM {escape_string_literal(str(csv_path))} "
                                 "WITH (format csv, NULL '', delimiter ',', header)")


def experiments_table():
    R = json.loads((OUT / "product_results.json").read_text(encoding="utf-8"))
    rows = []

    def add(exp, read, metric, r, decision, srm_p=None, n=None, kind="rel"):
        rows.append(dict(experiment=exp, read=read, metric=metric, estimate=r[kind], ci_low=r[f"{kind}_low"] if kind == "rel" else r["ci_low"],
                         ci_high=r[f"{kind}_high"] if kind == "rel" else r["ci_high"], p_value=r.get("p"), srm_p=srm_p,
                         users=n if n is not None else (r.get("n_t", 0) + r.get("n_c", 0)), decision=decision))
    e1 = R["E1"]
    add("E1 Paywall price", "Day 1 (misleading)", "Revenue per user, relative", e1["rev_d1"], "Do not decide on day 1", e1["srm"]["p"])
    add("E1 Paywall price", "Day 30 (decision)", "Revenue per user, relative", e1["rev_d30"], "Ship $19.99, watch refunds", e1["srm"]["p"])
    add("E1 Paywall price", "Day 30", "Conversion to paid, relative", e1["conv_d30"], "Expected: fewer but higher payers", e1["srm"]["p"])
    e2 = R["E2"]
    add("E2 Onboarding", "Raw (SRM)", "Onboarding completion, relative", e2["naive"], "Invalid: SRM on Android", e2["srm_all"]["p"])
    add("E2 Onboarding", "iOS only", "Onboarding completion, relative", e2["ios_only"], "Fix logging, re-run on Android", e2["srm_ios"]["p"])
    add("E2 Onboarding", "Intent-to-treat (hash)", "Onboarding completion, relative", e2["itt"], "Real but smaller gain", None)
    e3 = R["E3"]
    add("E3 Smart picks", "User split (biased)", "Matches per user, relative", e3["naive"], "Overstated by interference", None)
    c = e3["cluster"]
    rows.append(dict(experiment="E3 Smart picks", read="Metro clusters", metric="Matches per user, relative", estimate=c["rel"], ci_low=c["rel_low"],
                     ci_high=c["rel_high"], p_value=c["p"], srm_p=None, users=c["n_metros_t"] + c["n_metros_c"], decision="Extend cluster test 4 more weeks"))
    for r in R["E4"]["table"]:
        name = r["experiment"].split("_", 1)[1].replace("_", " ")
        rows.append(dict(experiment=f"E4 {name}", read=f"Raw p {r['p']:.3f} / Holm {r['p_holm']:.2f}", metric="Return within 7 days, relative",
                         estimate=r["rel"], ci_low=r["rel_low"], ci_high=r["rel_high"], p_value=r["p_holm"], srm_p=None, users=None,
                         decision="No effect after correction"))
    f = R["E5"]["final"]
    add("E5 Profile prompt", "Day 28 (planned end)", "Activation, relative", f, "No effect: the day-7 'win' was peeking", None, f["users"])
    e6 = R["E6"]
    add("E6 Ice-breakers", "Raw", "Messages per user, relative", e6["raw"], "Ship", None)
    add("E6 Ice-breakers", "CUPED", "Messages per user, relative", e6["adjusted"], "Ship: same answer, 30% less variance", None)
    add("E6 Ice-breakers", "CUPED, half the users", "Messages per user, relative", e6["half_sample_cuped"], "Same conclusion with half the sample", None)
    return pd.DataFrame(rows)


def main():
    utf8()
    TAB.mkdir(parents=True, exist_ok=True)
    con = sim_con()
    frames = {name: con.sql(q).df() for name, q in SIM_QUERIES.items()}
    frames["experiments"] = experiments_table()
    lk = pd.read_csv(PUB / "appstore_lookup.csv")
    frames["market_ratings"] = lk[["app", "focus", "country", "avg_rating", "rating_count", "current_version_date", "seller"]]
    frames["market_prices"] = pd.read_csv(OUT / "pub_price_by_country.csv")
    frames["review_themes"] = pd.read_csv(OUT / "pub_review_themes.csv")
    t = pd.read_csv(OUT / "pub_trends_weekly.csv", parse_dates=["date"])
    frames["trends"] = t[t["request"] == "US_focus"][["date", "term", "interest"]]
    schemas = {}
    d = duckdb.connect()
    for name, df in frames.items():
        for c in df.select_dtypes(include=["datetime", "datetimetz"]).columns:
            df[c] = pd.to_datetime(df[c]).dt.date          # dates, not timestamps, in Tableau
        path = TAB / f"{name}.csv"
        df.to_csv(path, index=False, date_format="%Y-%m-%d")
        d.register("x", df)
        schema = [(c, tableau_type(ty)) for c, ty, *_ in d.execute("describe x").fetchall()]
        d.unregister("x")
        schemas[name] = schema
        write_hyper(path, TAB / f"{name}.hyper", schema)
        print(f"{name:15s} {len(df):>8,} rows -> {name}.csv + .hyper")
    (TAB / "schemas.json").write_text(json.dumps(schemas, indent=1))


if __name__ == "__main__":
    main()

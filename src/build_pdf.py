"""Build the 8-page PDF report (16:9) and one PNG per page for the README.

Steps: read data/output (analysis_public.py, analysis_product.py) -> matplotlib charts as inline SVG ->
build/report.html -> PDF with Edge/Chrome headless -> empty PDF metadata -> PNG per page in docs/img/.
Every number in the text is read from the outputs; only published facts are typed, with their source.
Usage:  python src/build_pdf.py   (after the analyses and src/build_dashboard.py)
"""
import base64
import html
import json
import shutil
import subprocess
import sys
import tempfile

import numpy as np
import pandas as pd
from pypdf import PdfReader, PdfWriter

from charts import fig, pct_axis, thousands_axis, to_svg
from common import (BG, BLUE, BLUE_DARK, BLUE_LIGHT, BORDER, CARD, DISCLAIMER, DOCS, GREY, GREY_LIGHT, INK, INK2, MUTED, OUT,
                    PUB, RED, ROOT, ai_note, fmt_int, fmt_pct, utf8)

BUILD = ROOT / "build"
PDF = DOCS / "appflame_Hily_Taimi_growth_case_study.pdf"
TITLE = "appflame: finding and testing growth opportunities in Hily and Taimi"
SUBTITLE = ("Public app-store, pricing and search data, a real speed-dating dataset and a simulated dating-app event log, "
            "turned into growth hypotheses, rigorous A/B tests and a Tableau dashboard")


def browser():
    for p in [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Google\Chrome\Application\chrome.exe", shutil.which("msedge") or "", shutil.which("google-chrome") or "",
              shutil.which("chromium") or ""]:
        if p and __import__("pathlib").Path(p).exists():
            return p
    sys.exit("Edge or Chrome is needed to print the PDF.")


def headless(args):
    profile = tempfile.mkdtemp(prefix="edge-profile-")
    subprocess.run([browser(), "--headless=new", "--disable-gpu", "--no-first-run", "--hide-scrollbars",
                    f"--user-data-dir={profile}", *args], check=True, capture_output=True, timeout=240)
    shutil.rmtree(profile, ignore_errors=True)


# ------------------------------------------------------------------ html blocks
def card(title, body, cls="", style=""):
    t = f"<h3>{title}</h3>" if title else ""
    return f'<div class="card {cls}" style="{style}">{t}{body}</div>'


def kpi(tag, value, text, color=INK):
    return f'<div class="card kpi"><div class="ktag">{tag}</div><div class="kval" style="color:{color}">{value}</div><div class="ktxt">{text}</div></div>'


def table(rows, cols, cls="tight"):
    head = "".join(f"<th{' class=num' if n else ''}>{html.escape(h)}</th>" for h, n in cols)
    body = "".join("<tr>" + "".join(f"<td{' class=num' if cols[i][1] else ''}>{c}</td>" for i, c in enumerate(r)) + "</tr>" for r in rows)
    return f'<table class="{cls}"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def page(n, title, subtitle, tag, body, footer):
    tag_html = f'<div class="tag">{tag}</div>' if tag else ""
    return f"""<section class="page" id="p{n}">
  <header><div><h1>{title}</h1><p class="subtitle">{subtitle}</p></div>{tag_html}</header>
  <main>{body}</main>
  <footer><span>{footer}</span><span>{DISCLAIMER} · {n + 1}/8</span></footer>
</section>"""


CSS = f"""
@page {{ size: 1280px 720px; margin: 0; }}
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; padding: 0; background: {BG}; color: {INK}; font-family: "Segoe UI", system-ui, sans-serif; }}
.page {{ width: 1280px; height: 720px; padding: 24px 34px 0 34px; position: relative; overflow: hidden; page-break-after: always;
        break-after: page; background: {BG}; display: flex; flex-direction: column; }}
.page:last-child {{ page-break-after: auto; break-after: auto; }}
header {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 24px; min-height: 60px; }}
h1 {{ font-size: 22px; line-height: 1.2; margin: 0 0 4px 0; font-weight: 700; max-width: 1060px; }}
.subtitle {{ color: {INK2}; font-size: 12.3px; line-height: 1.38; margin: 0; max-width: 1080px; }}
.tag {{ font-size: 10.5px; font-weight: 700; letter-spacing: .07em; color: {INK2}; white-space: nowrap; padding: 4px 8px;
       border: 1px solid {BORDER}; border-radius: 4px; background: {CARD}; }}
main {{ flex: 1; display: grid; gap: 11px; margin-top: 10px; min-height: 0; }}
footer {{ color: {MUTED}; font-size: 9px; padding: 6px 0 8px 0; display: flex; justify-content: space-between; gap: 20px; }}
.card {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 8px; padding: 10px 13px; min-height: 0; overflow: hidden; }}
.card h3 {{ font-size: 12.3px; margin: 0 0 6px 0; font-weight: 600; }}
.card p, .card li {{ font-size: 11.2px; line-height: 1.4; color: {INK}; }}
.card p {{ margin: 0 0 5px 0; }}
.card ul, .card ol {{ margin: 0; padding-left: 16px; }} .card li {{ margin-bottom: 3px; }}
.muted {{ color: {INK2}; }} .small {{ font-size: 10.3px !important; }}
.kpi {{ display: flex; flex-direction: column; }}
.ktag {{ font-size: 9.3px; font-weight: 700; letter-spacing: .06em; color: {INK2}; }}
.kval {{ font-size: 26px; font-weight: 700; margin: 2px 0 2px 0; line-height: 1.1; }}
.ktxt {{ font-size: 10.6px; color: {INK2}; line-height: 1.33; }}
svg.chart {{ width: 100%; height: auto; display: block; }}
table {{ border-collapse: collapse; width: 100%; font-size: 10.8px; }}
th {{ text-align: left; color: {INK2}; font-weight: 600; border-bottom: 1px solid {INK2}; padding: 3px 5px; }}
td {{ border-bottom: 1px solid {BORDER}; padding: 3px 5px; vertical-align: top; }}
td.num, th.num {{ text-align: right; white-space: nowrap; }}
table.tight td, table.tight th {{ padding: 2px 5px; font-size: 10.2px; }}
.bad {{ color: {RED}; font-weight: 600; }} .good {{ color: {BLUE}; font-weight: 600; }}
.q {{ display: flex; gap: 10px; margin-bottom: 5px; font-size: 11.3px; line-height: 1.36; }}
.q b {{ color: {BLUE}; white-space: nowrap; min-width: 128px; }}
code, pre {{ font-family: Consolas, monospace; font-size: 9.8px; }}
pre {{ background: #F0EFEC; border-radius: 6px; padding: 6px 8px; margin: 4px 0 0 0; white-space: pre-wrap; line-height: 1.33; }}
.pill {{ display: inline-block; font-size: 9.3px; padding: 1px 6px; border-radius: 9px; background: #EAF2FC; color: {BLUE}; font-weight: 700; letter-spacing: .03em; }}
.pill.red {{ background: #FBEAEA; color: {RED}; }} .pill.grey {{ background: #EEEDE9; color: {INK2}; }}
.reco {{ border-left: 3px solid {BLUE}; padding: 1px 0 1px 9px; margin-bottom: 6px; font-size: 11.2px; line-height: 1.38; }}
.reco b {{ display: block; }}
.hyp {{ font-size: 10.6px; line-height: 1.38; background: #F3F7FD; border-radius: 6px; padding: 5px 7px; margin-top: 5px; }}
.grid {{ display: grid; gap: 11px; min-height: 0; }}
img.shot {{ width: 100%; border: 1px solid {BORDER}; border-radius: 6px; display: block; }}
"""


def sv(svg, h):
    """Cap a chart's rendered height (it keeps its aspect ratio, so nothing is cut)."""
    return svg.replace('<svg class="chart"', f'<svg class="chart" style="max-height:{h}px"', 1)


def g(cols, inner, rows=None):
    r = f"grid-template-rows:{rows};" if rows else ""
    return f'<div class="grid" style="grid-template-columns:{cols};{r}">{inner}</div>'


def ci(r, d=1):
    return f"{100 * r['rel']:+.{d}f}% [{100 * r['rel_low']:+.{d}f}, {100 * r['rel_high']:+.{d}f}]"


def pv(p):
    return "&lt;0.001" if p < 0.001 else f"{p:.3f}"


def csv(name):
    return pd.read_csv(OUT / name)


def bars_ci(labels, est, lo, hi, colors, w, h, xlabel=None, truth=None):
    f, ax = fig(w, h)
    y = np.arange(len(labels))[::-1]
    for yy, e, a, b, c in zip(y, est, lo, hi, colors):
        ax.plot([a, b], [yy, yy], color=INK2, lw=1.2)
        ax.scatter([e], [yy], color=c, s=34, zorder=5)
        ax.text(b + 0.005, yy, f"{e:+.1%}", va="center", fontsize=8, color=INK)
    ax.axvline(0, color=INK2, lw=0.8)
    if truth is not None:
        ax.axvline(truth, color=BLUE, lw=1, ls="--")
        ax.text(truth, len(labels) - 0.35, " true effect", color=BLUE, fontsize=7.5, va="bottom")
    ax.set_yticks(y, labels, fontsize=8.3, color=INK2)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="y", visible=False)
    pct_axis(ax, "x")
    ax.tick_params(axis="x", labelsize=7.5)
    ax.set_xlim(min(lo) - 0.02, max(hi) + 0.06)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=8)
    ax.spines["left"].set_visible(False)
    return to_svg(f)


# ------------------------------------------------------------------ pages
def p0(P, S):
    M, Rv, SD = P["market"], P["reviews"], P["speed_dating"]
    O, E1, E3 = S["opportunities"], S["E1"], S["E3"]
    qs = [("Where they stand", "How do Hily and Taimi compare with Tinder, Bumble, Hinge and others on ratings, price and search demand?"),
          ("What users say", "Which themes dominate written reviews, and what makes a match mutual in real dating data?"),
          ("Where the growth is", "Which funnel, market-balance, messaging and acquisition gaps can be turned into testable hypotheses?"),
          ("Trustworthy tests", "How should a test be sized, guarded and read so the decision survives SRM, peeking and multiple tests?"),
          ("Two-sided market", "Why do user-level tests mislead in dating, and what to run instead; how to decide with fewer users?")]
    qh = "".join(f'<div class="q"><b>{i + 1} · {a}</b><span>{html.escape(b)}</span></div>' for i, (a, b) in enumerate(qs))
    reco = [("Fix the Android photo step first.", f"Android users pass it at {fmt_pct(O['photo']['pass_android'])} vs {fmt_pct(O['photo']['pass_ios'])} on iOS: "
             f"about {fmt_int(O['photo']['extra_onboarded_per_month'])} more onboarded users a month in the simulated app."),
            ("Guarantee day-0 exposure to new profiles.", f"{fmt_pct(O['likes']['share_zero'])} of new users get no like on day 0 and come back half as often "
             f"({fmt_pct(O['likes']['return_d1_zero'])} vs {fmt_pct(O['likes']['return_d1_rest'])}). Real speed-dating data shows the same concentration."),
            ("Test matching features by metro, not by user.", f"A user-split test reported {E3['naive']['rel']:+.0%} matches; the metro-cluster test "
             f"{E3['cluster']['rel']:+.1%} (true effect +4%). Interference inflated the result about six-fold."),
            ("Decide prices on 30-day revenue, with a refund guardrail.", f"$19.99 lowers conversion ({ci(E1['conv_d30'], 0)}) but lifts 30-day revenue per user "
             f"({ci(E1['rev_d30'], 0)}); the first week looked far better because of novelty.")]
    rh = "".join(f'<div class="reco"><b>{a}</b><span class="muted">{b}</span></div>' for a, b in reco)
    k = (kpi("PUBLIC · US APP STORE", f"{M['hily_rating_us']:.1f}★ / {M['taimi_rating_us']:.1f}★",
             f"Hily ({fmt_int(M['hily_ratings_us'] / 1000)}K ratings, #{M['rank_ratings_hily']} of {M['n_peers']} by volume) and Taimi ({fmt_int(M['taimi_ratings_us'] / 1000)}K, #{M['rank_ratings_taimi']})")
         + kpi("PUBLIC · REVIEWS", fmt_pct(Rv['taimi_price']), f"of Taimi's written reviews (12 months) mention the paywall or price; Hily {fmt_pct(Rv['hily_price'])}, peers {fmt_pct(Rv['peers_price'])}", RED)
         + kpi("SIMULATED · INTERFERENCE", f"{E3['naive']['rel']:+.0%} → {E3['cluster']['rel']:+.0%}", "matching-feature effect: user-split test vs metro-cluster test (truth +4%)", BLUE)
         + kpi("SIMULATED · PRICE TEST", f"{E1['rev_d30']['rel']:+.0%}", f"30-day revenue per user at $19.99 vs $14.99, conversion {E1['conv_d30']['rel']:+.0%}", BLUE))
    meth = ('<p class="small"><span class="pill">PUBLIC DATA</span> appflame and Hily websites (facts as stated by the company), Apple App Store lookup API, store pages '
            f'and review RSS ({fmt_int(Rv["n_total"])} reviews, aggregates only), Google Trends, ECB rates, Match Group and Bumble filings, and the Columbia '
            f'speed-dating experiment ({fmt_int(SD["participants"])} people, {fmt_int(SD["rows"])} dates).</p>'
            '<p class="small"><span class="pill grey">SIMULATED</span> "App H", a fictional dating app: 200,000 sign-ups over 6 months, 4 countries, 6 channels, '
            'a ClickHouse-style event log calibrated on public benchmarks, with 6 planted A/B tests and a hidden truth file read only at the end. '
            'Never presented as appflame data.</p><p class="small">Tools: DuckDB SQL (14 queries, ClickHouse notes), Python (pandas, SciPy, scikit-learn), Tableau, HTML.</p>')
    req = table([("Spot growth opportunities alone, turn them into hypotheses", "4 opportunities → if / then / because, metric, guardrails, n", "4"),
                 ("Design, analyse and recommend A/B tests end to end", "6 tests: sizing, SRM, peeking, multiple tests, interference, CUPED", "5-7"),
                 ("SQL, Tableau, solid statistics", "14 DuckDB queries + ClickHouse notes; Tableau workbook; src/ab_stats.py", "5-8"),
                 ("Dating / social discovery, predictive models", "speed-dating match model, review themes, churn model", "3, 7")],
                [("What the role asks", False), ("Where it is shown", False), ("Page", True)])
    body = g("1fr", g("repeat(4, 1fr)", k) + g("1.05fr 1fr", card("Five questions, the work the role asks for", qh + '<div style="height:8px"></div>' + req)
                                                + g("1fr", card("Recommendations", rh) + card("Methods", meth), rows="auto auto")), rows="auto 1fr")
    return page(0, TITLE, SUBTITLE, "OVERVIEW", body, "Sources: data/SOURCES.md · simulation assumptions: data/ASSUMPTIONS.md")


def p1(P, S):
    M, T = P["market"], P["trends"]
    facts = pd.read_csv(PUB / "company_facts.csv")
    fct = facts.set_index(["entity", "fact"])["value"]
    us = csv("pub_ratings_us.csv").sort_values("rating_count")
    f, ax = fig(560, 230)
    y = np.arange(len(us))
    ax.barh(y, us["rating_count"], color=[BLUE if x else GREY_LIGHT for x in us["focus"]], height=0.66)
    for yy, (n, r) in enumerate(zip(us["rating_count"], us["avg_rating"])):
        ax.text(n + 15000, yy, f"{r:.2f}★", va="center", fontsize=8, color=INK)
    ax.set_yticks(y, us["app"], fontsize=8.3, color=INK2)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="y", visible=False)
    thousands_axis(ax, "x")
    ax.tick_params(axis="x", labelsize=7.5)
    ax.set_xlim(0, us["rating_count"].max() * 1.13)
    ax.spines["left"].set_visible(False)
    ratings_svg = to_svg(f)
    px = csv("pub_price_by_country.csv")
    order = ["US", "CA", "AU", "GB", "DE", "FR"]
    f, ax = fig(560, 175)
    x = np.arange(len(order))
    for i, (app, col) in enumerate((("Hily", BLUE), ("Taimi", BLUE_DARK))):
        v = px[px.app == app].set_index("country").reindex(order)["price_usd"]
        ax.bar(x + (i - 0.5) * 0.38, v, width=0.38, color=col, label=f"{app}: {px[px.app == app]['item'].iloc[0]}")
        for xx, vv in zip(x, v):
            ax.text(xx + (i - 0.5) * 0.38, vv + 0.4, f"${vv:.0f}", ha="center", fontsize=7, color=INK2)
    ax.set_xticks(x, [c + ("*" if c in ("GB", "DE", "FR") else "") for c in order], fontsize=8)
    ax.set_ylabel("USD", fontsize=8)
    ax.tick_params(axis="y", labelsize=7.5)
    ax.legend(fontsize=7.3, frameon=False, loc="upper left")
    ax.set_ylim(0, px["price_usd"].max() * 1.3)
    ax.grid(axis="x", visible=False)
    price_svg = to_svg(f)
    t = csv("pub_trends_weekly.csv")
    t = t[t["request"] == "US_focus"].copy()
    t["date"] = pd.to_datetime(t["date"])
    f, ax = fig(560, 150)
    for term, col, lw in (("Hily", BLUE, 1.8), ("Taimi", BLUE_DARK, 1.8), ("HER app", GREY, 1.1)):
        s = t[t.term == term].set_index("date")["interest"].rolling(4).mean()
        ax.plot(s.index, s.values, color=col, lw=lw, label=term)
    ax.legend(fontsize=7.5, frameon=False, ncol=3, loc="upper left")
    ax.tick_params(labelsize=7.5)
    ax.set_ylim(0, 35)
    ax.grid(axis="x", visible=False)
    trends_svg = to_svg(f)
    cad = P["reviews"]["cadence"]
    fc = (f'<ul class="small"><li><b>appflame</b>: "{html.escape(fct[("appflame", "Description")])}"; {fct[("appflame", "Company age")].split(" (")[0]}, '
          f'{fct[("appflame", "Team size")].split(" (")[0]} (website, seen 15 Nov 2026).</li>'
          f'<li><b>Position</b>: Hily and Taimi in the top 5 U.S. dating apps, 70M+ users, <i>as stated by appflame</i> in the job post.</li>'
          f'<li><b>Hily</b> ("Hey, I Like You!"): downloads {fct[("Hily", "Downloads")]}, mutual matches {fct[("Hily", "Mutual matches")]}, '
          f'likes sent {fct[("Hily", "Likes sent")]}, <i>as stated by Hily</i> (hily.com).</li>'
          '<li><b>Taimi</b>: inclusive LGBTQ+ dating app (appflame.com). taimi.com refuses automated requests; not collected.</li></ul>')
    rel = (f'<p class="small">Release rhythm (distinct app versions seen in reviews, last 90 days, per 30 days): Hily <b>{cad["Hily"]}</b>, '
           f'Taimi <b>{cad["Taimi"]}</b>, Bumble {cad["Bumble"]}, Tinder {cad["Tinder"]}, Hinge {cad["Hinge"]}. Both apps ship often, Hily faster than any peer.</p>')
    body = g("1fr 1fr", g("1fr", card("Published facts (appflame.com, hily.com, job post; no logo, figures as stated by the company)", fc + rel)
                                  + card("US App Store: Hily and Taimi hold peer-level ratings with far fewer reviews than the giants", sv(ratings_svg, 238)
                                         + f'<p class="small muted">iTunes lookup API, US storefront, {M["collected"]}. Bar = number of ratings, label = average rating.</p>'), rows="auto 1fr")
                        + g("1fr", card(f"Europe pays about {fmt_pct(M['eu_premium'])} more than the US for the same week of Hily Premium", sv(price_svg, 182)
                                        + f'<p class="small muted">Public App Store "In-App Purchases" lists, converted with ECB rates of {M["fx_date"]}. '
                                          '*GB, DE, FR prices include 19-20% VAT; US, CA, AU prices exclude sales tax, so part of the gap is tax.</p>')
                            + card("US search interest is small but rising (Google Trends, 4-week average)", sv(trends_svg, 150)
                                   + f'<p class="small muted">Hily {T["hily_us_2023"]:.1f} → {T["hily_us_2026"]:.1f} and Taimi {T["taimi_us_2023"]:.1f} → {T["taimi_us_2026"]:.1f} '
                                     f'(2023 → 2026 average, same request as Grindr at {T["grindr_us_2026"]:.0f}). Both names are also first names: upper bound.</p>'), rows="auto auto"))
    return page(1, "Hily and Taimi rate as well as the category leaders (4.4★) on a fraction of their review volume; they ship weekly and price higher in Europe",
                "Where the two apps stand in public data: published company facts, App Store ratings against ten peers, the real price list by storefront, release rhythm and search demand.",
                "PUBLIC DATA", body, "Apple iTunes Lookup API and public App Store pages (15 Nov 2026), Google Trends (pytrends), ECB reference rates, appflame.com, hily.com")


def p2(P, S):
    Rv, SD = P["reviews"], P["speed_dating"]
    th = csv("pub_review_themes.csv")
    themes = ["Paywall & price", "Fake profiles & scams", "Few matches, distance, reach", "Billing & refunds", "Bans & blocked accounts",
              "Bugs & technical", "Support", "Positive experience"]
    piv = th.pivot(index="theme", columns="app", values="share").reindex(themes)
    piv["Peers"] = piv[["Tinder", "Bumble", "Hinge"]].mean(axis=1)
    f, ax = fig(560, 235)
    y = np.arange(len(themes))[::-1]
    for i, (col, c) in enumerate((("Hily", BLUE), ("Taimi", BLUE_DARK), ("Peers", GREY_LIGHT))):
        ax.barh(y + (1 - i) * 0.27, piv[col], height=0.26, color=c, label=col if col != "Peers" else "Tinder, Bumble, Hinge (avg)")
    ax.set_yticks(y, themes, fontsize=8.2, color=INK2)
    ax.tick_params(axis="y", length=0)
    pct_axis(ax, "x")
    ax.tick_params(axis="x", labelsize=7.5)
    ax.grid(axis="y", visible=False)
    ax.legend(fontsize=7.3, frameon=False, loc="lower right")
    ax.spines["left"].set_visible(False)
    themes_svg = to_svg(f)
    md = csv("pub_sd_models.csv")
    f, ax = fig(330, 165)
    x = np.arange(len(md))
    ax.bar(x - 0.19, md["auc_lr"], 0.38, color=BLUE, label="logistic regression")
    ax.bar(x + 0.19, md["auc_gb"], 0.38, color=GREY_LIGHT, label="gradient boosting")
    for xx, v in zip(x, md["auc_lr"]):
        ax.text(xx - 0.19, v + 0.01, f"{v:.2f}", ha="center", fontsize=7.5)
    ax.set_xticks(x, ["profile only", "+ behaviour\nhistory", "+ ratings after\nmeeting"], fontsize=7.5)
    ax.set_ylim(0.5, 0.92)
    ax.axhline(0.5, color=INK2, lw=0.6)
    ax.set_ylabel("AUC (5 folds by wave)", fontsize=7.5)
    ax.tick_params(axis="y", labelsize=7)
    ax.legend(fontsize=6.8, frameon=False, loc="upper left")
    ax.grid(axis="x", visible=False)
    auc_svg = to_svg(f)
    sh = csv("pub_sd_by_shared.csv")
    f, ax = fig(250, 165)
    ax.bar(sh.iloc[:, 0].astype(str), sh["match_rate"], color=[BLUE_LIGHT, BLUE_LIGHT, BLUE, BLUE_DARK])
    for i, v in enumerate(sh["match_rate"]):
        ax.text(i, v + 0.01, f"{v:.0%}", ha="center", fontsize=7.5)
    pct_axis(ax, "y")
    ax.set_xlabel("lower of the two shared-interest ratings (0-10)", fontsize=7.2)
    ax.tick_params(labelsize=7)
    ax.grid(axis="x", visible=False)
    shar_svg = to_svg(f)
    mods = SD["models"]
    body = g("1fr 1.12fr",
             g("1fr", card("Written reviews: paywall and fake-profile complaints are well above peers", sv(themes_svg, 245)
                           + f'<p class="small muted">{fmt_int(Rv["n_last12m"])} App Store reviews of the last 12 months (US, GB, CA, AU for Hily and Taimi; US for peers), '
                             f'transparent keyword rules checked on {Rv["n_validation"]} hand-labelled reviews (precision {fmt_pct(Rv["micro_precision"])}, '
                             f'recall {fmt_pct(Rv["micro_recall"])}). Written reviews skew negative (avg {Rv["hily_avg"]:.1f}★ Hily, {Rv["taimi_avg"]:.1f}★ Taimi vs 4.4★ overall): '
                             'read them for themes, not for satisfaction. Aggregates only, no nickname stored.</p>')
               + card("What it means for the product", f'<ul class="small"><li><b>Paywall clarity</b>: {fmt_pct(Rv["taimi_price"])} (Taimi) and {fmt_pct(Rv["hily_price"])} (Hily) of reviews '
                      f'mention price or the paywall, vs {fmt_pct(Rv["peers_price"])} for peers: blurred "admirers" and tier names are the recurring friction. A paywall test '
                      'must watch refunds and 1-star reviews, not only conversion (page 7).</li><li><b>Trust</b>: fake profiles and scams in '
                      f'{fmt_pct(Rv["taimi_fake"])} / {fmt_pct(Rv["hily_fake"])} of reviews (peers {fmt_pct(Rv["peers_fake"])}): verification is a growth lever, not only safety.</li></ul>'), rows="1fr auto")
             + g("1fr", card(f"Speed dating: interest is rarely mutual. {fmt_pct(SD['yes_rate'])} say yes, only {fmt_pct(SD['match_rate'])} of dates match",
                           f'<p class="small">Columbia speed-dating experiment (Fisman & Iyengar): {fmt_int(SD["participants"])} people, {SD["waves"]} sessions, both decisions recorded. '
                           f'If yeses were independent, {fmt_pct(SD["independent_match"], 1)} would match; the real rate is {fmt_pct(SD["match_rate"], 1)} '
                           f'(correlation of the two decisions {SD["corr_dec"]:+.2f}). Likes concentrate: the 10% most-liked people receive {fmt_pct(SD["top10_share_yes"])} of all yeses.</p>')
               + g("1.3fr 1fr", card("A match model: behaviour beats profile data", sv(auc_svg, 175)
                                     + f'<p class="small muted">One row per pair ({fmt_int(SD["pairs"])}), whole sessions held out. Profile: shared-interest score, age gap, field, going-out habits. '
                                       'History: how often each person says yes and is said yes to, elsewhere (leave-one-out). No origin, religion, income or gender variable used.</p>')
                     + card("Shared interests felt on both sides", sv(shar_svg, 175)
                            + f'<p class="small muted">Measured interest overlap barely moves the match rate ({fmt_pct(SD["match_intcorr_q1"])} → {fmt_pct(SD["match_intcorr_q4"])}, '
                              'bottom to top quartile); <i>perceived</i> shared interests do.</p>'))
               + card("Product translation", '<ul class="small"><li><b>Rank for reciprocity</b>: score a pair by P(A likes B) x P(B likes A), using like-back history; '
                      f'profile fields alone reach AUC {mods["profile"]["auc_lr"]:.2f}, adding behaviour {mods["profile_history"]["auc_lr"]:.2f}.</li>'
                      '<li><b>Spread attention</b>: concentration of likes is natural, so new profiles need guaranteed exposure (opportunity 2).</li>'
                      '<li><b>Make common ground visible</b>: prompts and ice-breakers that surface shared interests (tested in E6, page 6).</li></ul>'), rows="auto 1fr auto"))
    return page(2, "Users complain about the paywall and fake profiles more than on peer apps; real dating data shows matches need two-sided signals, not profiles",
                "What users say in their own words, and what makes a match mutual: review themes against peers, then a predictive model on a real speed-dating experiment.",
                "PUBLIC DATA", body, "Apple review RSS (most recent, 15 Nov 2026), labels: data/public/review_validation_labels.csv · Speed Dating Data, Fisman & Iyengar, Columbia University")


def p3(P, S):
    O = S["opportunities"]
    fun = csv("p_funnel.csv")
    steps = ["1_basic_info", "2_birthday", "3_interests", "4_photo_upload", "5_bio", "6_location"]
    f, ax = fig(270, 185)
    x = np.arange(len(steps))
    for i, (pl, c) in enumerate((("ios", BLUE_LIGHT), ("android", BLUE))):
        v = fun[fun.platform == pl].set_index("step").reindex(steps)["share_of_signups"]
        ax.plot(x, v, marker="o", ms=3, color=c, lw=1.6, label=pl)
    ax.annotate("photo step", xy=(4, 0.56), xytext=(1.3, 0.6), fontsize=7, color=RED, arrowprops=dict(arrowstyle="->", color=RED, lw=0.8))
    ax.set_xticks(x, ["info", "birth", "interests", "photo", "bio", "location"], fontsize=6.5)
    pct_axis(ax, "y")
    ax.tick_params(axis="y", labelsize=6.5)
    ax.legend(fontsize=6.5, frameon=False, loc="lower left")
    ax.set_ylim(0.45, 1.02)
    f1 = to_svg(f)
    lb = csv("p_like_balance.csv")
    f, ax = fig(270, 185)
    ax.bar(lb["likes_bucket"].astype(str), lb["return_d1"], color=[RED] + [BLUE] * (len(lb) - 1))
    for i, (v, s) in enumerate(zip(lb["return_d1"], lb["share_of_users"])):
        ax.text(i, v + 0.01, f"{v:.0%}", ha="center", fontsize=6.8)
    pct_axis(ax, "y")
    ax.set_xlabel("likes received on day 0", fontsize=6.8)
    ax.set_ylabel("back on day 1", fontsize=6.8)
    ax.tick_params(labelsize=6.5)
    ax.grid(axis="x", visible=False)
    f2 = to_svg(f)
    ph = csv("p_push_hour.csv")
    f, ax = fig(270, 185)
    ax.bar(ph["local_hour"], ph["open_rate"], color=[BLUE if 19 <= h <= 21 else GREY_LIGHT for h in ph["local_hour"]])
    ax.errorbar(ph["local_hour"], ph["open_rate"], yerr=ph["open_rate_moe95"], fmt="none", ecolor=INK2, lw=0.6)
    pct_axis(ax, "y")
    ax.set_xlabel("local send hour", fontsize=6.8)
    ax.set_ylabel("open rate", fontsize=6.8)
    ax.tick_params(labelsize=6.5)
    ax.grid(axis="x", visible=False)
    f3 = to_svg(f)
    ch = csv("p_channels.csv")
    ch = ch[ch.channel != "organic"].sort_values("roas_to_date")
    f, ax = fig(270, 185)
    ax.barh(ch["channel"], ch["roas_to_date"], color=[RED if c == "tiktok" else BLUE for c in ch["channel"]], height=0.6)
    ax.axvline(1, color=INK2, lw=0.8, ls="--")
    for i, v in enumerate(ch["roas_to_date"]):
        ax.text(v + 0.02, i, f"{v:.2f}", va="center", fontsize=6.8)
    ax.set_xlabel("revenue to date / spend (May-Jul cohorts)", fontsize=6.8)
    ax.tick_params(labelsize=6.5)
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, ch["roas_to_date"].max() * 1.2)
    f4 = to_svg(f)

    def opp(n, title, chart, facts, o):
        return card(f"{n} · {title}", sv(chart, 205) + f'<p class="small">{facts}</p>'
                    + f'<div class="hyp"><b>Hypothesis.</b> {html.escape(o["hypothesis"])}<br><b>Primary metric:</b> {o["metric"]}. '
                      f'<b>Guardrails:</b> {o["guardrails"]}.' + (f' <b>Size:</b> {fmt_int(o["n_per_arm"])} users per arm.' if "n_per_arm" in o else "")
                    + (f' <b>Design:</b> {o["design"]}.' if "design" in o else "") + "</div>")
    a, b, c, d = O["photo"], O["likes"], O["push"], O["channel"]
    body = g("1fr 1fr 1fr 1fr",
             opp(1, "Android loses a third of users at the photo step", f1,
                 f'Pass rate out of the photo step: Android <b>{fmt_pct(a["pass_android"])}</b>, iOS {fmt_pct(a["pass_ios"])}. Closing the gap: '
                 f'~{fmt_int(a["extra_onboarded_per_month"])} more onboarded users a month, ~${fmt_int(a["revenue_per_month"])} a month at ${a["value_per_onboarded"]:.2f} per onboarded user.', a)
             + opp(2, "One new user in ten gets no like on day 0", f2,
                   f'{fmt_pct(b["share_zero"])} of new profiles receive no like on day 0; {fmt_pct(b["share_side_a_in_zero"])} of them sit on the crowded side of the market. '
                   f'They return on day 1 at <b>{fmt_pct(b["return_d1_zero"])}</b> vs {fmt_pct(b["return_d1_rest"])}. Top 10% of new profiles get {fmt_pct(b["top10_share"])} of likes (Gini {b["gini_day0_likes"]:.2f}).', b)
             + opp(3, "Evening pushes are opened 1.5x more often", f3,
                   f'The scheduler sets the hour from a hash of the user id, a natural experiment. 19-21h: open rate <b>{fmt_pct(c["open_19_21"], 1)}</b> vs {fmt_pct(c["open_all"], 1)} on average; '
                   f'same-day return {fmt_pct(c["return_19_21"], 1)} vs {fmt_pct(c["return_all"], 1)} (~{fmt_int(c["extra_returns_per_month"])} extra returns a month).', c)
             + opp(4, "TikTok sign-ups are cheap but do not pay back", f4,
                   f'Cost ${d["tiktok_cps"]:.2f} per sign-up (lowest), but day-30 activity {fmt_pct(d["tiktok_d30"])} vs {fmt_pct(d["organic_d30"])} organic, payer share {fmt_pct(d["tiktok_payer"], 1)}, '
                   f'revenue ${d["tiktok_rev"]:.2f} per sign-up: ROAS <b>{d["tiktok_roas"]:.2f}</b> after 90+ days (${fmt_int(d["tiktok_spend_6m"] / 1000)}K spent in 6 months).', d))
    return page(3, "Four growth opportunities found in the event log, each turned into a testable hypothesis with a metric, guardrails and a sample size",
                "Exploration of the simulated funnel, market balance, messaging and acquisition data, before any test: where users are lost, why, and what to try first.",
                "SIMULATED", body, "SIMULATED data (seed 42): sql/01, sql/06, sql/07, sql/08 · hypotheses: docs/PRODUCT_MEMO_example.md")


def p4(P, S):
    E1, E2, E4, E5 = S["E1"], S["E2"], S["E4"], S["E5"]
    pre = E1["pre"]
    d5 = csv("p_e5_daily.csv")
    f, ax = fig(560, 170)
    ax.plot(d5["day"], d5["z"].abs(), color=BLUE, lw=1.8, label="|z| of the cumulative read, each day")
    ax.axhline(1.96, color=RED, lw=1, ls="--", label="naive threshold 1.96 (p < 0.05)")
    ax.plot(d5["day"], d5["obf_z"], color=INK2, lw=1, label=f"O'Brien-Fleming boundary ({len(d5)} looks)")
    sig = d5[d5["p"] < 0.05]
    ax.scatter(sig["day"], sig["z"].abs(), color=RED, s=18, zorder=5)
    ax.set_ylim(0, 5)
    ax.set_xlabel("day of the test", fontsize=8)
    ax.legend(fontsize=7, frameon=False, loc="upper right")
    ax.tick_params(labelsize=7.5)
    ax.grid(axis="x", visible=False)
    e5_svg = to_svg(f)
    t4 = pd.DataFrame(E4["table"])
    labels = [f"{e.split('_', 1)[1].replace('_', ' ')}  p={p:.3f}, Holm {h:.2f}" for e, p, h in zip(t4["experiment"], t4["p"], t4["p_holm"])]
    e4_svg = bars_ci(labels, t4["rel"], t4["rel_low"], t4["rel_high"], [RED if p < 0.05 else GREY for p in t4["p"]], 560, 150,
                     "return within 7 days, relative effect, 95% CI (unadjusted)")
    srm = table([(f"<b>{lab}</b>", fmt_int(r["n_t"]), fmt_int(r["n_c"]), fmt_pct(r["share_t"], 1), f'{r["chi2"]:.1f}',
                  f'<span class="{"bad" if r["p"] < 0.001 else ""}">{pv(r["p"])}</span>')
                 for lab, r in (("All", E2["srm_all"]), ("Android", E2["srm_android"]), ("iOS", E2["srm_ios"]))],
                [("Platform", False), ("Treatment", True), ("Control", True), ("Share T", True), ("Chi²", True), ("p", True)])
    reads = table([(lab, f'{100 * r["diff"]:+.1f} pts', f'[{100 * r["ci_low"]:+.1f}, {100 * r["ci_high"]:+.1f}]') for lab, r in
                   (("Raw read (biased)", E2["naive"]), ("iOS only (no bug)", E2["ios_only"]), ("Intent-to-treat, rebuilt from the hash", E2["itt"]))],
                  [("Onboarding completion", False), ("Effect", True), ("95% CI", True)])
    size = table([("Baseline (May-Jun, no test)", f'${pre["mean"]:.2f} rev/user, sd ${pre["sd"]:.2f}', ""),
                  ("Detect +8% (80% power, 5% two-sided)", f'{fmt_int(pre["n_per_arm_8pct"])} per arm', f'{pre["days_needed_8pct"]:.0f} days'),
                  ("Detect +12%", f'{fmt_int(pre["n_per_arm_12pct"])} per arm', f'{pre["days_needed_12pct"]:.0f} days'),
                  ("Detect -10% on conversion", f'{fmt_int(pre["n_per_arm_conv_10pct"])} per arm', "")],
                 [("Paywall price test (E1) sizing", False), ("Users", True), ("At current traffic", True)])
    body = g("1fr 1.1fr",
             g("1fr", card("1 · Size before launch, from a pre-period", size + f'<p class="small">Revenue per user is zero for 96% of users, so its standard deviation is 5x its mean: '
                           f'n = 2(z<sub>0.975</sub>+z<sub>0.8</sub>)²σ²/δ². +8% would take {pre["days_needed_8pct"]:.0f} days of traffic; the team accepts a 12% minimum detectable effect and runs 8 weeks '
                           f'({fmt_int(E1["rev_d30"]["n_t"])} vs {fmt_int(E1["rev_d30"]["n_c"])} users). Guardrails fixed in advance: refunds, first renewal, day-30 activity, reports.</p>')
               + card("2 · Check the split before reading the result (onboarding test E2)", srm + reads
                      + f'<p class="small">The split is 50/50 on iOS but {fmt_pct(E2["srm_android"]["share_t"], 1)} on Android (p {pv(E2["srm_android"]["p"])}): exposure was logged only from step 3 for '
                        f'Android treatment users, so {fmt_int(E2["missing_android_treatment"])} early quitters vanished from treatment. The raw read doubles the effect. '
                        'Because assignment is a hash of the user id, the intended group of every sign-up can be rebuilt: the honest effect is about +3 points. Fix logging, re-run on Android.</p>'), rows="auto 1fr")
             + g("1fr", card(f"3 · Peeking: an A/A-like test looked significant on day {E5['first_sig_day']}, then the effect vanished", sv(e5_svg, 175)
                           + f'<p class="small">Profile-prompt test (E5), no real effect. Read every day, it crossed p < 0.05 on {E5["days_significant"]} days and ended at p = {E5["final"]["p"]:.2f}. '
                             f'In 2,000 simulated A/A tests with daily looks, <b>{fmt_pct(E5["aa"]["naive_daily"])}</b> show a "winner" at least once vs {fmt_pct(E5["aa"]["single_look"], 1)} with one planned look, '
                             f'and {fmt_pct(E5["aa"]["obf_daily"], 1)} with the O\'Brien-Fleming boundary (z = {E5["obf_c"]:.2f}/√t). Rule: fixed horizon, or a sequential boundary.</p>')
               + card("4 · Five tests at once: one 'winner' is a false positive", sv(e4_svg, 150)
                      + f'<p class="small">Five UI tests on the same users, none with a real effect. With five tests at α = 5%, the chance of at least one false winner is {fmt_pct(E4["fwer_5_tests"])}. '
                        'The dark paywall "wins" at p = 0.029; after Holm (family-wise) or Benjamini-Hochberg (false discovery rate) correction it does not. Pre-register one primary metric per test.</p>'), rows="1fr 1fr"))
    return page(4, "Size from a pre-period, check the split, fix the horizon, correct for multiple tests: each rule stopped a wrong decision here",
                "Designing tests that can be trusted: sample size and guardrails before launch; a sample-ratio mismatch, a peeking trap and a multiple-testing trap caught in the read-out.",
                "SIMULATED", body, "SIMULATED data: sql/09, sql/10 · statistics: src/ab_stats.py (z-test, Welch t-test, chi-square, Holm, BH, O'Brien-Fleming) · template: docs/EXPERIMENT_TEMPLATE.md")


def p5(P, S):
    E3, E6 = S["E3"], S["E6"]
    c = E3["cluster"]
    svg3 = bars_ci(["User split inside metros\n(standard A/B tool)", "Whole metros randomised\n(cluster test)"],
                   [E3["naive"]["rel"], c["rel"]], [E3["naive"]["rel_low"], c["rel_low"]], [E3["naive"]["rel_high"], c["rel_high"]],
                   [RED, BLUE], 520, 140, "matches per user, relative effect, 95% CI")
    t6 = csv("p_e6.csv")
    svg6 = bars_ci(t6["read"].tolist(), t6["rel"], t6["rel_low"], t6["rel_high"], [GREY, BLUE, GREY, BLUE], 520, 165,
                   "messages per user, relative effect, 95% CI")
    diag = f"""<svg viewBox="0 0 520 150" class="chart" style="max-height:150px" font-family="Segoe UI" font-size="10">
      <rect x="4" y="8" width="246" height="134" rx="8" fill="#FBEAEA" stroke="{BORDER}"/>
      <text x="14" y="26" font-weight="700" fill="{INK}">User split: treated and control share one pool</text>
      {''.join(f'<circle cx="{30 + 40 * i}" cy="60" r="11" fill="{BLUE if i % 2 == 0 else GREY_LIGHT}"/>' for i in range(6))}
      {''.join(f'<circle cx="{30 + 40 * i}" cy="110" r="11" fill="{GREY_LIGHT if i % 2 == 0 else BLUE}"/>' for i in range(6))}
      <path d="M30 71 L70 99 M110 71 L70 99 M190 71 L230 99" stroke="{RED}" stroke-width="1.4"/>
      <text x="14" y="138" fill="{INK2}" font-size="9">Treated users win attention that control users lose</text>
      <rect x="270" y="8" width="246" height="134" rx="8" fill="#EAF2FC" stroke="{BORDER}"/>
      <text x="280" y="26" font-weight="700" fill="{INK}">Cluster test: whole metros switch</text>
      {''.join(f'<circle cx="{296 + 30 * i}" cy="60" r="10" fill="{BLUE}"/>' for i in range(3))}
      {''.join(f'<circle cx="{416 + 30 * i}" cy="60" r="10" fill="{GREY_LIGHT}"/>' for i in range(3))}
      {''.join(f'<circle cx="{296 + 30 * i}" cy="105" r="10" fill="{BLUE}"/>' for i in range(3))}
      {''.join(f'<circle cx="{416 + 30 * i}" cy="105" r="10" fill="{GREY_LIGHT}"/>' for i in range(3))}
      <line x1="393" y1="40" x2="393" y2="122" stroke="{INK2}" stroke-dasharray="3,3"/>
      <text x="300" y="138" fill="{INK2}" font-size="9">metro A treated      |      metro B control</text></svg>"""
    body = g("1fr 1fr",
             g("1fr", card("Why dating tests are harder than shop tests", diag
                           + '<p class="small">A match needs two people. A feature that shows treated users to more people, or treated users more people, also changes what '
                             'control users see. Users are no longer independent units (the SUTVA assumption fails), so the treated-minus-control difference mixes the true effect '
                             'with attention moved from control to treatment.</p>')
               + card("Matching feature (E3): the user-split test overstated the effect about six-fold", sv(svg3, 150)
                      + f'<p class="small">Same feature, same month. In the 20 user-split metros, treated users got <b>{E3["naive"]["rel"]:+.1%}</b> matches vs control, partly because control users lost '
                        f'{fmt_pct(-E3["spillover_control_drop"], 0)} of their matches (control users inside split metros vs control metros). In the {c["n_metros_t"] + c["n_metros_c"]} cluster metros, the effect is '
                        f'<b>{c["rel"]:+.1%}</b> [{100 * c["rel_low"]:+.1f}, {100 * c["rel_high"]:+.1f}], p = {c["p"]:.2f}, analysed with one point per metro (test/pre-period ratio). '
                        'Wider interval, unbiased answer: extend the cluster test or add metros, and plan cluster or switchback designs for any feature that touches both sides.</p>'), rows="auto 1fr")
             + g("1fr", card(f"CUPED (E6 ice-breakers): the pre-period explains {fmt_pct(E6['var_reduction'])} of the variance", sv(svg6, 175)
                           + f'<p class="small">Metric: messages sent in the 14 days of the test; covariate: the same metric in the 14 days before (correlation {E6["rho"]:.2f}). '
                             f'y<sub>adj</sub> = y − θ(x − x̄), θ = cov(x, y)/var(x) = {E6["theta"]:.2f}. The mean effect does not change, the variance drops by about ρ²: '
                             f'raw {ci(E6["raw"])} vs CUPED {ci(E6["adjusted"])}.</p>')
               + card("Same decision with fewer users", table([
                   ("Users needed per arm for +5% (80% power)", fmt_int(E6["n_per_arm_raw_5pct"]), fmt_int(E6["n_per_arm_cuped_5pct"])),
                   ("Half the sample: effect [95% CI]", ci(E6["half_sample_raw"]), ci(E6["half_sample_cuped"])),
                   ("Half the sample: p-value", f'{E6["half_sample_raw"]["p"]:.2f}', f'{E6["half_sample_cuped"]["p"]:.3f}')],
                   [("", False), ("Raw", True), ("CUPED", True)])
                   + f'<p class="small">With half the users the raw read is inconclusive; CUPED reaches the same conclusion as the full test. In practice: shorter tests, or smaller detectable effects '
                     'at the same duration, for any metric with a stable pre-period (messages, sessions, matches). Covariates must be measured before assignment.</p>')
               + card("Decision", f'<p class="small"><b>Ship ice-breakers</b> ({ci(E6["adjusted"])} messages per user). <b>Do not ship Smart Picks on the user-split result</b>: '
                      'run the metro test 4 more weeks; the speed-dating evidence (page 3) supports the mechanism, the size is what is uncertain.</p>'), rows="auto auto auto"))
    return page(5, f"In a two-sided market, a user-split test reported {S['E3']['naive']['rel']:+.0%} matches and a metro-cluster test {S['E3']['cluster']['rel']:+.0%}: cluster tests remove the bias, CUPED buys back the power",
                "Testing where users interact: interference between test groups, a metro-cluster design that removes it, and variance reduction that reaches the same decision with fewer users.",
                "SIMULATED", body, "SIMULATED data: sql/11, sql/12 · cluster analysis at metro level, CUPED in src/ab_stats.py")


def truth_rows(S):
    # implied truths from the simulation parameters (src/simulate.py) -> compared with the estimates
    from simulate import PASS
    share_ios = 0.57
    ctrl = share_ios * np.prod(PASS["ios"]) + (1 - share_ios) * np.prod(PASS["android"])
    trt = share_ios * np.prod([1 - 0.9 * (1 - p) for p in PASS["ios"]]) + (1 - share_ios) * np.prod([1 - 0.9 * (1 - p) for p in PASS["android"]])
    E2, E3, E4, E5, E6 = S["E2"], S["E3"], S["E4"], S["E5"], S["E6"]
    false_pos = sum(r["p"] < 0.05 for r in E4["table"])
    adj = sum(r["p_holm"] < 0.05 for r in E4["table"])
    return [("E2 onboarding", f'{100 * (trt - ctrl):+.1f} pts', f'raw {100 * E2["naive"]["diff"]:+.1f} / ITT {100 * E2["itt"]["diff"]:+.1f} pts', "ITT"),
            ("E3 smart picks", "+4.0%", f'user split {E3["naive"]["rel"]:+.1%} / cluster {E3["cluster"]["rel"]:+.1%}', "cluster"),
            ("E4 five UI tests", "0 real effects", f'{false_pos} raw winner / {adj} after Holm', "Holm"),
            ("E5 profile prompt", "no effect", f'day {E5["first_sig_day"]} p < 0.05 / day 28 p = {E5["final"]["p"]:.2f}', "fixed horizon"),
            ("E6 ice-breakers", "+5.0%", f'raw {E6["raw"]["rel"]:+.1%} / CUPED {E6["adjusted"]["rel"]:+.1%}', "both")]


def p6(P, S):
    E1, C = S["E1"], S["churn"]
    wk = csv("p_e1_weekly.csv")
    f, ax = fig(560, 165)
    x = wk["week"]
    ax.fill_between(x, wk["rev_d30_low"], wk["rev_d30_high"], color=BLUE_LIGHT, alpha=0.35, lw=0)
    ax.plot(x, wk["rev_d30_rel"], color=BLUE, lw=1.8, marker="o", ms=3, label="30-day revenue per user (95% CI)")
    ax.plot(x, wk["conv_d1_rel"], color=RED, lw=1.4, marker="o", ms=3, label="conversion on day 1")
    ax.plot(x, wk["conv_rel"], color=RED, lw=1, ls=":", label="conversion within 30 days")
    ax.axhline(0, color=INK2, lw=0.8)
    ax.axhline(E1["rev_d30"]["rel"], color=BLUE, lw=0.8, ls="--")
    ax.annotate("novelty week", xy=(1, wk["conv_d1_rel"].iloc[0]), xytext=(2.0, wk["conv_d1_rel"].iloc[0] + 0.05), fontsize=7.5, color=RED,
                arrowprops=dict(arrowstyle="->", color=RED, lw=0.8))
    pct_axis(ax, "y")
    ax.set_xlabel("assignment week (1 = 1-7 July)", fontsize=8)
    ax.legend(fontsize=7, frameon=False, loc="upper right")
    ax.tick_params(labelsize=7.5)
    ax.grid(axis="x", visible=False)
    e1_svg = to_svg(f)
    cm = csv("p_churn_by_matches.csv")
    f, ax = fig(270, 140)
    ax.bar(cm["matches_7d_bucket"].astype(str), cm["churn_rate"], color=[RED, BLUE_LIGHT, BLUE, BLUE_DARK])
    for i, v in enumerate(cm["churn_rate"]):
        ax.text(i, v + 0.01, f"{v:.0%}", ha="center", fontsize=7)
    pct_axis(ax, "y")
    ax.set_xlabel("matches in the first 7 days of the subscription", fontsize=7)
    ax.set_ylabel("cancel at first renewal", fontsize=7)
    ax.tick_params(labelsize=7)
    ax.grid(axis="x", visible=False)
    churn_svg = to_svg(f)
    G = E1["guardrails"]
    met = table([("Conversion to paid, 30 days", ci(E1["conv_d30"]), pv(E1["conv_d30"]["p"])),
                 ("Revenue per user, day 1", ci(E1["rev_d1"]), pv(E1["rev_d1"]["p"])),
                 ("Revenue per user, day 30 (decision)", f'<b>{ci(E1["rev_d30"])}</b>', pv(E1["rev_d30"]["p"])),
                 ("First week only: conversion, day 1", ci(E1["week1_conv"]), pv(E1["week1_conv"]["p"])),
                 ("Guardrail: refund rate", f'{fmt_pct(G["refund_t"], 1)} vs {fmt_pct(G["refund_c"], 1)}', f'<span class="bad">{pv(G["refund_test"]["p"])}</span>'),
                 ("Guardrail: first renewal", f'{fmt_pct(G["renew1_t"], 1)} vs {fmt_pct(G["renew1_c"], 1)}', ""),
                 ("Guardrail: active days 28-32", f'{fmt_pct(G["active_d30_t"], 1)} vs {fmt_pct(G["active_d30_c"], 1)}', "")],
                [("Paywall $19.99 vs $14.99 (E1)", False), ("Effect [95% CI]", True), ("p", True)])
    img = DOCS / "img" / "tableau_3_experiments.png"       # screenshot of the Tableau dashboard (see docs/TABLEAU_BUILD.md)
    if not img.exists():
        img = DOCS / "img" / "dashboard_experiments.png"      # HTML fallback, same extracts
    shot = base64.b64encode(img.read_bytes()).decode()
    tr = table([(a, b, c_, d) for a, b, c_, d in truth_rows(S)], [("Test", False), ("Hidden truth", True), ("Estimates", False), ("Right read", False)])
    body = g("1.08fr 1fr",
             g("1fr", card("Price test: decide on 30-day revenue, not on the first days", sv(e1_svg, 170) + met
                           + f'<p class="small"><b>Decision: ship $19.99</b> with a clearer price screen; refunds rose ({fmt_pct(G["refund_t"], 1)} vs {fmt_pct(G["refund_c"], 1)}) and are already netted out of revenue. '
                             'Week 1 showed conversion <i>up</i>: curiosity about a new paywall, gone by week 2. Day-1 revenue overstates the gain because renewals come later. Re-check revenue at day 90.</p>'), rows="1fr")
             + g("1fr", card("Checked against the hidden truth (opened last, after every estimate was written)", tr)
                 + g("0.9fr 1.1fr", card("Churn model: who cancels at the first renewal", sv(churn_svg, 130)
                                         + f'<p class="small">{fmt_int(C["n"])} subscriptions, {fmt_pct(C["base_rate"])} cancel. Logistic regression AUC <b>{C["auc_lr"]:.2f}</b> '
                                           f'(gradient boosting {C["auc_gb"]:.2f}), 5-fold CV. Top decile cancels at {fmt_pct(C["top_decile_rate"])}, bottom decile {fmt_pct(C["bottom_decile_rate"])}: '
                                           'week-1 matches drive renewal, so a "first match" nudge for new payers is the lever.</p>')
                     + card("Tableau dashboard, experiments view (tableau/AppH_Product_Analytics.twbx; HTML fallback on the same extracts)", f'<img class="shot" src="data:image/png;base64,{shot}">')), rows="auto 1fr"))
    return page(6, f"Results and decisions: ship the $19.99 paywall ({E1['rev_d30']['rel']:+.0%} 30-day revenue per user, refunds watched) and nudge new payers to a first match",
                "The price test read the right way (novelty, day-30 revenue, guardrails), a churn model that tells product where to act, and every estimate checked against the hidden truth.",
                "SIMULATED", body, "SIMULATED data: sql/09, sql/13 · src/analysis_product.py · dashboard: docs/dashboard.html, tableau/")


def p7(P, S):
    body = g("1fr 1fr 1fr",
             g("1fr", card("Sources (all collected 15 Nov 2026)", '<ul class="small">'
                           '<li><b>appflame.com</b>, <b>hily.com</b> (read in a browser: both refuse scripts) and the Product Analyst job post: facts as stated by the company. taimi.com refuses automated requests: not collected.</li>'
                           '<li><b>Apple</b>: iTunes Lookup API, public App Store pages (paths allowed by robots.txt), customer-review RSS feed. 2 s between requests, no account.</li>'
                           '<li><b>Google Trends</b> via pytrends (relative 0-100 index). <b>ECB</b> euro reference rates.</li>'
                           '<li><b>Match Group</b> investor relations (payers, RPP) and <b>Bumble Inc.</b> 10-Q Q3 2026 (ARPPU): orders of magnitude for the simulation.</li>'
                           '<li><b>Speed Dating Experiment</b>, R. Fisman and S. Iyengar, Columbia Business School (Fisman et al., QJE 2006), public CSV distributed by Columbia University. '
                           'No licence text is attached: used for non-commercial, educational analysis, with citation.</li></ul>')
               + card("Privacy and respect", '<ul class="small"><li>Reviews: aggregates and themes only; nicknames dropped while parsing; review text stays local (not in the repository).</li>'
                      '<li>No sensitive attribute (orientation, religion, origin) analysed or inferred, including for Taimi; speed-dating race, religion, income and gender fields are not used.</li>'
                      '<li>The simulated "market side" is a neutral A/B label used only for market balance.</li><li>No appflame employee is named. No account created, nothing bought.</li></ul>'), rows="auto auto")
             + g("1fr", card("Limits", '<ul class="small"><li><b>Simulated is not real.</b> App H shows methods; its levels are plausible, not appflame\'s. Planted effects make the traps visible on purpose.</li>'
                           '<li>App Store figures are iOS only; Google Play was not collected. Written reviews are a negative, self-selected sample.</li>'
                           '<li>Store prices mix VAT-inclusive (EU, UK) and tax-exclusive (US, CA, AU) prices; listed items have no stated duration except the weekly plan.</li>'
                           '<li>Google Trends terms are also first names; values are relative within a request.</li>'
                           '<li>Speed dating: 2002-2004 students in New York, face-to-face. It informs mechanisms (reciprocity, concentration), not app parameters.</li>'
                           '<li>The O\'Brien-Fleming constant is calibrated by simulation for equally spaced daily looks.</li></ul>')
               + card("Deliverables", '<ul class="small"><li><b>sql/</b>: 14 commented DuckDB queries with ClickHouse equivalents (windowFunnel, retention, uniqExact, arrayJoin).</li>'
                      '<li><b>notebooks/</b>: one notebook, public data → hypotheses → tests → models.</li><li><b>docs/</b>: experiment template + 2 filled examples, product memo, Tableau build guide, HTML dashboard.</li>'
                      '<li><b>tableau/</b>: workbook on .hyper extracts, 4 dashboards.</li></ul>'), rows="auto auto")
             + g("1fr", card("Reproduce", '<pre>python -m venv .venv\n.venv\\Scripts\\pip install -r requirements.txt\npython src/download_data.py    # public data, ~10 min\npython src/simulate.py         # App H, seed 42\npython src/run_sql.py          # sql/ -> data/output\npython src/analysis_public.py\npython src/analysis_product.py\npython src/export_tableau.py   # CSV + .hyper\npython src/build_tableau.py\npython src/build_dashboard.py\npython src/build_pdf.py</pre>')
               + card("AI note", f'<p class="small">{html.escape(ai_note())}</p>'), rows="auto auto"))
    return page(7, "Methods, limits and AI note: every public figure is sourced and dated, every simulated one is labelled, and the whole study re-runs from one folder",
                "How the numbers were produced, under which terms, where they stop being reliable, and how to rebuild everything from scratch.", "", body,
                "README.md, data/SOURCES.md, data/ASSUMPTIONS.md")


def main():
    utf8()
    BUILD.mkdir(exist_ok=True)
    (DOCS / "img").mkdir(parents=True, exist_ok=True)
    P = json.loads((OUT / "public_results.json").read_text(encoding="utf-8"))
    S = json.loads((OUT / "product_results.json").read_text(encoding="utf-8"))
    headless(["--screenshot=" + str(DOCS / "img" / "dashboard_experiments.png"), "--window-size=1400,820", "--virtual-time-budget=8000",
              (DOCS / "dashboard.html").as_uri() + "#2"])
    pages = [p0(P, S), p1(P, S), p2(P, S), p3(P, S), p4(P, S), p5(P, S), p6(P, S), p7(P, S)]
    doc = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{html.escape(TITLE)}</title><meta name="author" content="">'
           f'<style>{CSS}</style></head><body>{"".join(pages)}</body></html>')
    report = BUILD / "report.html"
    report.write_text(doc, encoding="utf-8")
    raw_pdf = BUILD / "report_raw.pdf"
    headless([f"--print-to-pdf={raw_pdf}", "--no-pdf-header-footer", "--print-to-pdf-no-header", report.as_uri()])
    reader, writer = PdfReader(str(raw_pdf)), PdfWriter()
    for pg in reader.pages:
        writer.add_page(pg)
    writer.add_metadata({"/Title": TITLE, "/Author": "", "/Creator": "", "/Producer": "", "/Subject": "", "/Keywords": ""})
    with open(PDF, "wb") as fh:
        writer.write(fh)
    print(f"PDF: {PDF.relative_to(ROOT)} ({len(reader.pages)} pages)")
    names = ["00_overview", "01_public_market", "02_reviews_speed_dating", "03_growth_opportunities", "04_trustworthy_tests",
             "05_two_sided_market", "06_results_decisions", "07_methods"]
    for i, name in enumerate(names):
        single = BUILD / f"page_{i}.html"
        single.write_text(doc.replace("<body>", f"<body><style>.page{{display:none}} #p{i}{{display:flex}}</style>"), encoding="utf-8")
        headless([f"--screenshot={DOCS / 'img' / (name + '.png')}", "--window-size=1280,720", single.as_uri()])
    print("PNG pages written to docs/img/")


if __name__ == "__main__":
    main()

"""Collect the PUBLIC DATA used in the case study (no key, no account, low frequency).

1. Apple iTunes Lookup API: rating, number of ratings, version, release dates, genre, seller
   for Hily, Taimi and peer dating apps, in 4 English-speaking storefronts.
2. Public App Store pages (apps.apple.com/<cc>/app/id<id>): star distribution and the
   in-app purchase price list shown under "Information", for Hily and Taimi in 6 storefronts
   and for peers in the US. Only paths allowed by apps.apple.com/robots.txt are requested.
3. Apple customer-review RSS feed (most recent reviews, up to 10 pages x 50 per storefront).
   Privacy: the reviewer nickname and profile link are dropped while parsing, never written to disk.
4. Google Trends (unofficial pytrends client): relative search interest, 5 years, US + worldwide by country.
5. Speed Dating Experiment (Fisman & Iyengar, Columbia Business School), public CSV distributed by
   Columbia University (Gelman's ARM book data page).

Raw snapshots go to data/raw/ (git-ignored); tidy tables go to data/public/ (committed).
Usage:  python src/download_data.py            (about 10 minutes, mostly polite waiting)
"""
import json
import re
import time

import pandas as pd
from bs4 import BeautifulSoup

from common import PUB, RAW, TODAY, polite_get, save_json, utf8

FOCUS = {"Hily": 1250946975, "Taimi": 1282966364}
PEERS = {  # name -> App Store id (checked against trackName after each lookup)
    "Tinder": 547702041, "Bumble": 930441707, "Hinge": 595287172, "Grindr": 319881193,
    "OkCupid": 338701294, "Match": 305939712, "Plenty of Fish": 389638243, "Badoo": 351331194,
    "HER": 573328837,
}
LOOKUP_COUNTRIES = ["us", "gb", "ca", "au"]
PRICE_COUNTRIES = ["us", "gb", "ca", "au", "de", "fr"]
REVIEW_COUNTRIES = ["us", "gb", "ca", "au"]
REVIEW_APPS = {**FOCUS, "Tinder": PEERS["Tinder"], "Bumble": PEERS["Bumble"], "Hinge": PEERS["Hinge"]}
SPEED_DATING_URL = "http://www.stat.columbia.edu/~gelman/arm/examples/speed.dating/Speed%20Dating%20Data.csv"
SPEED_DATING_KEY = "http://www.stat.columbia.edu/~gelman/arm/examples/speed.dating/Speed%20Dating%20Data%20Key.doc"


# ---------------------------------------------------------------- 1. lookup API
def lookup():
    rows = []
    ids = {**FOCUS, **PEERS}
    for cc in LOOKUP_COUNTRIES:
        r = polite_get(f"https://itunes.apple.com/lookup?id={','.join(map(str, ids.values()))}&country={cc}")
        save_json(r.json(), RAW / "lookup" / f"lookup_{cc}_{TODAY}.json")
        by_id = {a["trackId"]: a for a in r.json().get("results", [])}
        for name, tid in ids.items():
            a = by_id.get(tid)
            if not a:
                print(f"  lookup: {name} not in {cc} store")
                continue
            rows.append({
                "app": name, "focus": name in FOCUS, "country": cc, "track_id": tid, "track_name": a["trackName"],
                "seller": a.get("sellerName"), "genre": a.get("primaryGenreName"),
                "avg_rating": a.get("averageUserRating"), "rating_count": a.get("userRatingCount"),
                "current_version": a.get("version"), "current_version_date": (a.get("currentVersionReleaseDate") or "")[:10],
                "first_release_date": (a.get("releaseDate") or "")[:10], "content_rating": a.get("contentAdvisoryRating"),
                "size_mb": round(int(a.get("fileSizeBytes") or 0) / 1e6, 1), "collected": TODAY,
            })
    df = pd.DataFrame(rows)
    df.to_csv(PUB / "appstore_lookup.csv", index=False)
    print(f"lookup: {len(df)} app x storefront rows")
    return df


# ---------------------------------------------------------------- 2. store pages
def _price(text):
    """'$14.99' -> 14.99 ; '14,99 €' -> 14.99 ; '£9.99' -> 9.99 ; 'CA$19.99' -> 19.99"""
    t = text.replace("\xa0", " ").replace(" ", " ")
    m = re.search(r"(\d[\d .,]*)", t)
    if not m:
        return None
    n = m.group(1).strip().replace(" ", "")
    if "," in n and (n.rfind(",") > n.rfind(".")):
        n = n.replace(".", "").replace(",", ".")
    else:
        n = n.replace(",", "")
    return float(n)


CURRENCY = {"us": "USD", "ca": "CAD", "au": "AUD", "gb": "GBP", "de": "EUR", "fr": "EUR"}  # each storefront shows "$" for CAD/AUD


def parse_store_page(html):
    tag = BeautifulSoup(html, "lxml").find("script", id="serialized-server-data")
    if not tag:
        return None
    txt = tag.string
    out = {"iap": []}
    m = re.search(r'"ratingAverage":\s*([\d.]+)', txt)
    out["avg_rating"] = float(m.group(1)) if m else None
    m = re.search(r'"totalNumberOfRatings":\s*(\d+)', txt)
    out["rating_count"] = int(m.group(1)) if m else None
    m = re.search(r'"ratingCounts":\s*\[([\d,\s]+)\]', txt)
    out["stars_5_to_1"] = [int(x) for x in m.group(1).split(",")] if m else None
    data = json.loads(txt)

    def walk(o):
        if isinstance(o, dict):
            if o.get("$kind") == "Annotation" and o.get("items") and any(
                    i.get("$kind") == "textPair" and i.get("trailingText") for i in o["items"] if isinstance(i, dict)):
                if any(c in (o.get("title") or "") for c in ("Purchase", "Achats", "Käufe", "In-App")):
                    for i in o["items"]:
                        if isinstance(i, dict) and i.get("$kind") == "textPair":
                            out["iap"].append((i["leadingText"].strip(), i["trailingText"].strip()))
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(data)
    return out


def store_pages():
    stars, iap = [], []
    jobs = [(n, i, cc) for n, i in FOCUS.items() for cc in PRICE_COUNTRIES] + [(n, i, "us") for n, i in PEERS.items()]
    for name, tid, cc in jobs:
        r = polite_get(f"https://apps.apple.com/{cc}/app/id{tid}", allow_redirects=True)
        r.encoding = "utf-8"
        if r.status_code != 200:
            print(f"  page {name} {cc}: HTTP {r.status_code}")
            continue
        (RAW / "pages").mkdir(parents=True, exist_ok=True)
        (RAW / "pages" / f"{name.replace(' ', '_')}_{cc}_{TODAY}.html").write_text(r.text, encoding="utf-8")
        p = parse_store_page(r.text)
        if not p:
            continue
        s = p["stars_5_to_1"] or [None] * 5
        stars.append({"app": name, "country": cc, "avg_rating": p["avg_rating"], "rating_count": p["rating_count"],
                      **{f"stars_{5 - k}": s[k] for k in range(5)}, "collected": TODAY})
        for rank, (item, price) in enumerate(p["iap"], 1):
            iap.append({"app": name, "country": cc, "rank_on_page": rank, "item": item, "price_text": price,
                        "price": _price(price), "currency": CURRENCY[cc], "collected": TODAY})
    pd.DataFrame(stars).to_csv(PUB / "appstore_stars.csv", index=False)
    pd.DataFrame(iap).to_csv(PUB / "appstore_iap_prices.csv", index=False)
    print(f"store pages: {len(stars)} pages, {len(iap)} in-app purchase lines")


# ---------------------------------------------------------------- 3. review RSS
def reviews():
    rows = []
    for name, tid in REVIEW_APPS.items():
        countries = REVIEW_COUNTRIES if name in FOCUS else ["us"]
        for cc in countries:
            for page in range(1, 11):
                url = f"https://itunes.apple.com/{cc}/rss/customerreviews/page={page}/id={tid}/sortby=mostrecent/json"
                r = polite_get(url)
                if r.status_code != 200:
                    break
                entries = r.json().get("feed", {}).get("entry", [])
                if isinstance(entries, dict):
                    entries = [entries]
                entries = [e for e in entries if "im:rating" in e]
                if not entries:
                    break
                for e in entries:  # author name / uri deliberately not read
                    rows.append({"app": name, "country": cc, "review_id": e["id"]["label"],
                                 "date": e["updated"]["label"][:10], "rating": int(e["im:rating"]["label"]),
                                 "version": e.get("im:version", {}).get("label"), "title": e["title"]["label"],
                                 "text": e["content"]["label"], "collected": TODAY})
            print(f"  reviews {name} {cc}: {sum(1 for x in rows if x['app'] == name and x['country'] == cc)}")
    if not rows:   # the feed is sometimes empty for every app (seen on 11 and 16 Nov 2026): keep the earlier snapshot
        print("reviews: the RSS feed returned no review today; earlier snapshot kept (or published aggregates reused)")
        return None
    df = pd.DataFrame(rows).drop_duplicates("review_id")
    (RAW / "reviews").mkdir(parents=True, exist_ok=True)
    df.to_parquet(RAW / "reviews" / f"reviews_{TODAY}.parquet", index=False)  # text stays local (raw)
    print(f"reviews: {len(df)} unique reviews")
    return df


# ---------------------------------------------------------------- 4. Google Trends
def trends():
    from pytrends.request import TrendReq
    out = RAW / "trends"
    out.mkdir(parents=True, exist_ok=True)
    jobs = [("US_brands", ["Hily", "Taimi", "Bumble", "Hinge", "Tinder"], "US", "today 5-y"),
            ("US_focus", ["Hily", "Taimi", "Grindr", "HER app"], "US", "today 5-y"),
            ("WW_focus", ["Hily", "Taimi"], "", "today 5-y")]
    frames = []
    for key, terms, geo, tf in jobs:
        for attempt in range(4):
            try:
                c = TrendReq(hl="en-US", tz=0, timeout=(10, 30))
                c.build_payload(terms, timeframe=tf, geo=geo)
                df = c.interest_over_time().drop(columns="isPartial", errors="ignore")
                df.to_csv(out / f"{key}_{TODAY}.csv")
                long = df.reset_index().melt(id_vars="date", var_name="term", value_name="interest")
                long["request"], long["geo"] = key, geo or "WORLD"
                frames.append(long)
                if key == "WW_focus":
                    reg = c.interest_by_region(resolution="COUNTRY", inc_low_vol=False).reset_index()
                    reg.to_csv(PUB / "trends_by_country.csv", index=False)
                print(f"  trends {key}: {len(df)} weeks")
                break
            except Exception as exc:
                print(f"  trends {key}: attempt {attempt + 1} failed ({type(exc).__name__}), waiting")
                time.sleep(60 * (attempt + 1))
        time.sleep(20)
    if frames:
        pd.concat(frames).to_csv(PUB / "trends_weekly.csv", index=False)


# ---------------------------------------------------------------- 4b. exchange rates
def fx():
    """ECB euro reference rates of the collection day (public XML), to compare store prices in USD."""
    import xml.etree.ElementTree as ET
    r = polite_get("https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml")
    (RAW / "fx").mkdir(parents=True, exist_ok=True)
    (RAW / "fx" / f"ecb_{TODAY}.xml").write_bytes(r.content)
    root = ET.fromstring(r.content)
    cube = [c for c in root.iter() if c.get("currency")]
    day_ = next(c.get("time") for c in root.iter() if c.get("time"))
    eur = {c.get("currency"): float(c.get("rate")) for c in cube}          # 1 EUR = x currency
    rows = [{"currency": cur, "usd_per_unit": eur["USD"] / (1.0 if cur == "EUR" else eur[cur]), "ecb_date": day_}
            for cur in ("USD", "EUR", "GBP", "CAD", "AUD")]
    pd.DataFrame(rows).to_csv(PUB / "fx_ecb.csv", index=False)
    print(f"fx: ECB rates of {day_}")


# ---------------------------------------------------------------- 5. speed dating
def speed_dating():
    dest = RAW / "speed_dating"
    dest.mkdir(parents=True, exist_ok=True)
    for url, fn in ((SPEED_DATING_URL, "Speed Dating Data.csv"), (SPEED_DATING_KEY, "Speed Dating Data Key.doc")):
        if (dest / fn).exists():
            continue
        r = polite_get(url)
        r.raise_for_status()
        (dest / fn).write_bytes(r.content)
    df = pd.read_csv(dest / "Speed Dating Data.csv", encoding="latin-1")
    print(f"speed dating: {len(df):,} rows (one per person x date), {df['iid'].nunique()} participants")


if __name__ == "__main__":
    utf8()
    PUB.mkdir(parents=True, exist_ok=True)
    import sys
    steps = sys.argv[1:] or ["lookup", "pages", "reviews", "trends", "fx", "speed"]
    if "lookup" in steps:
        lookup()
    if "pages" in steps:
        store_pages()
    if "reviews" in steps:
        reviews()
    if "trends" in steps:
        trends()
    if "fx" in steps:
        fx()
    if "speed" in steps:
        speed_dating()
